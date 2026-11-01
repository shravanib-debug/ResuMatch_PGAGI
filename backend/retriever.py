"""
retriever.py — Hybrid Retrieval Pipeline
=========================================
Retrieval strategy (in order):
  1. Multi-query expansion     — LLM generates 3 targeted queries from resume + role
  2. Semantic search           — ChromaDB cosine similarity per query
  3. BM25 keyword search       — exact term matching per query
  4. Score fusion              — weighted merge, deduplication by chunk ID
  5. Cross-encoder reranking   — re-scores top candidates query+chunk together
  6. CRAG validation           — LLM checks if chunks are sufficient; reformulates once if not

Why each step exists:
  - Multi-query  : one query formulation misses angles; 3 queries cast a wider net
  - Semantic     : finds conceptually related content even with different vocabulary
  - BM25         : finds exact ML terms ('backpropagation', 'softmax') semantic search misses
  - Reranking    : cross-encoders are far more accurate than cosine similarity alone
  - CRAG         : catches cases where retrieval simply failed; one self-correction loop

Usage:
    from pipeline.retriever import HybridRetriever
    retriever = HybridRetriever()
    chunks = retriever.retrieve(parsed_resume, role="aiml", prior_topics=[])
    context = retriever.build_context_string(chunks)

Requirements (add to requirements.txt):
    chromadb
    sentence-transformers
    rank_bm25
    anthropic
    numpy
"""

import os
import re
import json
import pickle
import logging
import numpy as np

import chromadb
from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from rank_bm25 import BM25Okapi
from google import genai
from dataclasses import dataclass

# ── Logging ───────────────────────────────────────────────────────────────────

log = logging.getLogger(__name__)

from config import get_settings

# ── Config ────────────────────────────────────────────────────────────────────

CHROMA_PATH     = "./chroma_db"
BM25_PATH       = "./bm25_indexes"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL  = "Xenova/ms-marco-MiniLM-L-6-v2"
LLM_MODEL       = get_settings().llm_model

# Retrieval knobs
SEMANTIC_CANDIDATES = 10   # fetch this many from ChromaDB per query before reranking
BM25_CANDIDATES     = 10   # fetch this many from BM25 per query before reranking
FINAL_TOP_K         = 5    # chunks returned to question generator after reranking
MIN_SIMILARITY      = 0.30  # discard semantic results below this score
SEMANTIC_WEIGHT     = 0.6  # weight for semantic scores in fusion
BM25_WEIGHT         = 0.4  # weight for BM25 scores in fusion (must sum to 1.0)

# CRAG
CRAG_ENABLED        = False
CRAG_MIN_SCORE      = 0.45  # if best chunk after reranking is below this, trigger CRAG


# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class RetrievedChunk:
    """A chunk returned by the retriever, ready for prompt injection."""
    id: str
    text: str
    source: str
    section_title: str
    page_num: int
    role: str
    score: float            # final score after fusion + reranking
    retrieval_method: str   # 'semantic', 'bm25', or 'hybrid'


@dataclass
class RetrievalResult:
    """Full retrieval result including diagnostics."""
    chunks: list[RetrievedChunk]
    queries_used: list[str]
    crag_triggered: bool = False
    crag_reformulated_query: str = ""


# ── HybridRetriever ───────────────────────────────────────────────────────────

class HybridRetriever:
    """
    Stateful retriever. Loads models once on init, reuses across calls.
    Designed to be instantiated once at app startup and injected as a dependency.
    """

    def __init__(self):
        log.info("Initialising HybridRetriever...")

        # Embedding model (same as ingestion — must match)
        log.info(f"  Loading embedding model: {EMBEDDING_MODEL}")
        self.embedder = TextEmbedding(EMBEDDING_MODEL, threads=1)

        # Cross-encoder reranker
        log.info(f"  Loading reranker: {RERANKER_MODEL}")
        self.reranker = TextCrossEncoder(RERANKER_MODEL, threads=1)

        # ChromaDB client
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

        # BM25 indexes: loaded per role, cached after first load
        self._bm25_cache: dict[str, dict] = {}

        # Google Gemini client
        self.llm = genai.Client(api_key=os.getenv("GOOGLE_API_KEY", ""))

        log.info("  HybridRetriever ready.")

    # ── Public API ────────────────────────────────────────────────────────────

    def retrieve(
        self,
        parsed_resume: dict,
        role: str,
        prior_topics: list[str],
        top_k: int = FINAL_TOP_K,
    ) -> RetrievalResult:
        """
        Full retrieval pipeline: query construction → hybrid search →
        reranking → CRAG validation.

        Args:
            parsed_resume : structured resume dict from resume_service
            role          : 'aiml' or 'datascience'
            prior_topics  : list of topic strings already covered this session
            top_k         : number of final chunks to return

        Returns:
            RetrievalResult with chunks and diagnostic metadata
        """
        # Step 1: LLM constructs 3 targeted queries
        queries = self._construct_queries(parsed_resume, role, prior_topics)
        log.info(f"Queries constructed: {queries}")

        # Step 2 + 3 + 4: hybrid search across all queries
        fused_chunks = self._hybrid_search(queries, role, top_k=top_k * 2)

        # Step 5: cross-encoder reranking
        # Use the first (most important) query as the reranking reference
        reranked = self._rerank(queries[0], fused_chunks, top_k=top_k)

        crag_triggered = False
        crag_query = ""

        # Step 6: CRAG — validate quality, self-correct once if needed
        if CRAG_ENABLED and reranked:
            best_score = reranked[0].score
            if best_score < CRAG_MIN_SCORE:
                log.info(
                    f"CRAG triggered (best score {best_score:.3f} < {CRAG_MIN_SCORE}). "
                    "Reformulating query..."
                )
                crag_triggered = True
                crag_query = self._crag_reformulate(queries, parsed_resume, role)

                if crag_query:
                    # One more retrieval pass with reformulated query
                    extra_chunks = self._hybrid_search([crag_query], role, top_k=top_k * 2)
                    combined = self._deduplicate(reranked + extra_chunks)
                    reranked = self._rerank(crag_query, combined, top_k=top_k)

        return RetrievalResult(
            chunks=reranked,
            queries_used=queries,
            crag_triggered=crag_triggered,
            crag_reformulated_query=crag_query,
        )

    def build_context_string(self, chunks: list[RetrievedChunk]) -> str:
        """
        Formats chunks into a readable context block for LLM prompt injection.
        Includes section metadata so the LLM knows the pedagogical source.

        Example output:
            [Context 1] (Section: 3.2 Gradient Descent | Source: mitchell_ml.pdf | Score: 0.87)
            Gradient descent is an optimisation algorithm that...
        """
        if not chunks:
            return "No relevant context retrieved."

        parts = []
        for i, chunk in enumerate(chunks, start=1):
            header = (
                f"[Context {i}] "
                f"(Section: {chunk.section_title} | "
                f"Source: {os.path.basename(chunk.source)} | "
                f"Score: {chunk.score:.2f})"
            )
            parts.append(f"{header}\n{chunk.text}")

        return "\n\n---\n\n".join(parts)

    # ── Step 1: Query Construction ────────────────────────────────────────────

    def _construct_queries(
        self,
        parsed_resume: dict,
        role: str,
        prior_topics: list[str],
    ) -> list[str]:
        """
        Builds 3 retrieval queries based on the candidate's
        resume, the target role, and topics already covered.
        
        Now completely bypasses the LLM to save on API calls/rate limits,
        relying entirely on heuristic fallback queries.
        """
        skills  = parsed_resume.get("skills", [])[:8]
        domains = parsed_resume.get("domains", [])
        
        # Directly build queries from resume data (0 API calls)
        return self._fallback_queries(skills, domains, role, prior_topics)

    def _fallback_queries(
        self,
        skills: list[str],
        domains: list[str],
        role: str,
        prior_topics: list[str],
    ) -> list[str]:
        """Heuristic query construction when LLM call fails."""
        queries = []
        unused_skills = [s for s in skills if s.lower() not in " ".join(prior_topics).lower()]

        if unused_skills:
            queries.append(f"{unused_skills[0]} concepts and applications")
        if len(unused_skills) > 1:
            queries.append(f"{unused_skills[1]} algorithms and implementation")
        if domains:
            queries.append(f"{domains[0]} {role} technical fundamentals")

        # Pad to 3 if needed
        while len(queries) < 3:
            queries.append(f"{role} core technical concepts")

        return queries[:3]

    # ── Step 2: Semantic Search ───────────────────────────────────────────────

    def _semantic_search(
        self,
        query: str,
        role: str,
        top_k: int,
    ) -> list[dict]:
        """
        Query ChromaDB with a single query string.
        Returns list of raw result dicts with normalised similarity scores.
        """
        collection_name = f"{role}_knowledge"

        try:
            collection = self.chroma_client.get_collection(collection_name)
        except Exception:
            raise ValueError(
                f"ChromaDB collection '{collection_name}' not found. "
                "Run pipeline/ingest.py first."
            )

        query_embedding = next(iter(self.embedder.embed([query]))).tolist()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        docs      = results["documents"][0]
        metas     = results["metadatas"][0]
        distances = results["distances"][0]
        ids       = results["ids"][0]

        chunks = []
        for doc, meta, dist, chunk_id in zip(docs, metas, distances, ids):
            # ChromaDB cosine distance: 0=identical, 2=opposite → convert to 0–1 similarity
            similarity = max(0.0, 1.0 - (dist / 2.0))
            if similarity < MIN_SIMILARITY:
                continue
            chunks.append({
                "id": chunk_id,
                "text": doc,
                "metadata": meta,
                "semantic_score": similarity,
                "bm25_score": 0.0,
                "retrieval_method": "semantic",
            })

        return chunks

    # ── Step 3: BM25 Keyword Search ───────────────────────────────────────────

    def _load_bm25(self, role: str) -> dict:
        """Load and cache BM25 index for a role from disk."""
        if role not in self._bm25_cache:
            index_path = os.path.join(BM25_PATH, f"{role}_bm25.pkl")
            if not os.path.exists(index_path):
                raise FileNotFoundError(
                    f"BM25 index not found at {index_path}. "
                    "Run pipeline/ingest.py first."
                )
            with open(index_path, "rb") as f:
                self._bm25_cache[role] = pickle.load(f)
            log.info(f"BM25 index loaded for role '{role}'")

        return self._bm25_cache[role]

    def _bm25_search(
        self,
        query: str,
        role: str,
        top_k: int,
    ) -> list[dict]:
        """
        BM25 keyword search over the pickled index.
        Returns list of raw result dicts with normalised BM25 scores.
        """
        try:
            index_data = self._load_bm25(role)
        except FileNotFoundError as e:
            log.warning(f"BM25 search skipped: {e}")
            return []

        bm25: BM25Okapi         = index_data["bm25"]
        chunk_ids: list[str]    = index_data["chunk_ids"]
        chunk_texts: list[str]  = index_data["chunk_texts"]
        chunk_metas: list[dict] = index_data["chunk_metadatas"]

        # Tokenise query the same way as ingestion
        tokenised_query = re.findall(r"[a-z0-9]+", query.lower())
        raw_scores = bm25.get_scores(tokenised_query)

        # Normalise BM25 scores to 0–1
        max_score = raw_scores.max() if raw_scores.max() > 0 else 1.0
        normalised = raw_scores / max_score

        # Get top_k indices by score
        top_indices = np.argsort(normalised)[::-1][:top_k]

        chunks = []
        for idx in top_indices:
            score = float(normalised[idx])
            if score < 0.01:   # skip near-zero scores
                continue
            chunks.append({
                "id": chunk_ids[idx],
                "text": chunk_texts[idx],
                "metadata": chunk_metas[idx],
                "semantic_score": 0.0,
                "bm25_score": score,
                "retrieval_method": "bm25",
            })

        return chunks

    # ── Step 4: Score Fusion ──────────────────────────────────────────────────

    def _hybrid_search(
        self,
        queries: list[str],
        role: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """
        Run semantic + BM25 search for every query.
        Merge all results, fuse scores for chunks found by both methods,
        deduplicate by chunk ID.
        """
        # Collect all raw results across queries and methods
        all_raw: dict[str, dict] = {}  # chunk_id → merged result dict

        for query in queries:
            semantic_results = self._semantic_search(query, role, SEMANTIC_CANDIDATES)
            bm25_results     = self._bm25_search(query, role, BM25_CANDIDATES)

            for r in semantic_results + bm25_results:
                cid = r["id"]
                if cid not in all_raw:
                    all_raw[cid] = r.copy()
                else:
                    # Chunk found by multiple queries/methods — take best scores
                    all_raw[cid]["semantic_score"] = max(
                        all_raw[cid]["semantic_score"], r["semantic_score"]
                    )
                    all_raw[cid]["bm25_score"] = max(
                        all_raw[cid]["bm25_score"], r["bm25_score"]
                    )
                    # Update method label
                    if all_raw[cid]["retrieval_method"] != r["retrieval_method"]:
                        all_raw[cid]["retrieval_method"] = "hybrid"

        # Compute fused score and convert to RetrievedChunk objects
        fused: list[RetrievedChunk] = []
        for cid, r in all_raw.items():
            fused_score = (
                SEMANTIC_WEIGHT * r["semantic_score"]
                + BM25_WEIGHT * r["bm25_score"]
            )
            meta = r["metadata"]
            fused.append(RetrievedChunk(
                id=cid,
                text=r["text"],
                source=meta.get("source", ""),
                section_title=meta.get("section_title", ""),
                page_num=meta.get("page_num", 0),
                role=meta.get("role", role),
                score=round(fused_score, 4),
                retrieval_method=r["retrieval_method"],
            ))

        # Sort by fused score, return top candidates for reranking
        fused.sort(key=lambda x: x.score, reverse=True)
        return fused[:top_k]

    # ── Step 5: Cross-Encoder Reranking ──────────────────────────────────────

    def _rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """
        Use a cross-encoder to re-score each (query, chunk) pair.

        Unlike bi-encoders (which embed query and chunk independently),
        cross-encoders see both together — dramatically more accurate.
        Scores are merged with the fusion score so both signals contribute.
        """
        if not chunks:
            return []

        ce_scores = np.array(list(self.reranker.rerank(query, [chunk.text for chunk in chunks], batch_size=4)))

        # Normalise cross-encoder scores to 0–1 range
        ce_min, ce_max = ce_scores.min(), ce_scores.max()
        if ce_max > ce_min:
            ce_normalised = (ce_scores - ce_min) / (ce_max - ce_min)
        else:
            ce_normalised = np.ones(len(ce_scores)) * 0.5

        # Blend cross-encoder score with fusion score (70/30 in favour of CE)
        # Store original fusion scores to avoid mutation issues during CRAG retry
        fusion_scores = [chunk.score for chunk in chunks]
        for i, chunk in enumerate(chunks):
            blended = 0.7 * float(ce_normalised[i]) + 0.3 * fusion_scores[i]
            chunk.score = round(blended, 4)

        chunks.sort(key=lambda x: x.score, reverse=True)
        return chunks[:top_k]

    # ── Step 6: CRAG Validation ───────────────────────────────────────────────

    def _crag_reformulate(
        self,
        original_queries: list[str],
        parsed_resume: dict,
        role: str,
    ) -> str:
        """
        Corrective RAG: ask the LLM to reformulate the query when retrieved
        chunks scored too low, implying the knowledge base wasn't hit well.

        Returns a single reformulated query string, or "" if LLM call fails.
        """
        skills = parsed_resume.get("skills", [])[:5]

        prompt = f"""These search queries failed to retrieve sufficiently relevant content from ML textbooks:

Queries tried: {json.dumps(original_queries)}
Candidate skills: {", ".join(skills)}
Role: {role}

The retrieved content scored below the quality threshold. Generate ONE alternative search query
that approaches the topic differently — use different vocabulary, synonyms, or a related
sub-topic that might be better represented in textbooks.

Respond with ONLY the query string. No explanation, no quotes, no JSON.
Example: support vector machine kernel functions classification
"""

        try:
            response = self.llm.models.generate_content(
                model=LLM_MODEL,
                contents=prompt,
            )
            reformulated = response.text.strip().strip('"').strip("'")
            log.info(f"CRAG reformulated query: '{reformulated}'")
            return reformulated

        except Exception as e:
            log.warning(f"CRAG LLM call failed: {e}")
            return ""

    # ── Utility ───────────────────────────────────────────────────────────────

    def _deduplicate(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Deduplicate by chunk ID, keeping the highest-scored version."""
        seen: dict[str, RetrievedChunk] = {}
        for chunk in chunks:
            if chunk.id not in seen or chunk.score > seen[chunk.id].score:
                seen[chunk.id] = chunk
        return list(seen.values())