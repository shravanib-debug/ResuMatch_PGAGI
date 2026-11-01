"""
ingest.py — Knowledge Base Ingestion Pipeline
==============================================
Upgrades over plain RAG:
  1. Cross-page semantic chunking  — page boundaries are metadata only, never
                                     chunking boundaries. Topics that span pages
                                     stay in the same chunk.
  2. Robust sentence splitting     — abbreviation-safe (e.g., i.e., Fig., Eq.,
                                     et al., decimals). Uses spacy when available,
                                     falls back to protected-regex otherwise.
  3. Section-aware metadata        — every chunk knows its chapter/section title,
                                     cleaned to a single readable line.
  4. BM25 index                    — built over same chunks for hybrid retrieval.

Run once per knowledge base update:
    cd backend
    python ingest.py

Requirements (add to requirements.txt):
    pdfplumber
    sentence-transformers
    chromadb
    rank_bm25
    langchain-text-splitters
    tqdm
    numpy
    spacy                        # optional but strongly recommended
    # after installing spacy:
    # python -m spacy download en_core_web_sm
"""

import os
import re
import uuid
import pickle
import logging
import numpy as np
import pdfplumber
import chromadb

from tqdm import tqdm
from dataclasses import dataclass
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Spacy (optional — better sentence splitting) ──────────────────────────────

try:
    import spacy
    _nlp = spacy.load("en_core_web_sm", disable=["ner", "tagger", "parser", "lemmatizer"])
    _nlp.add_pipe("sentencizer")
    _nlp.max_length = 5_000_000  # handle large PDFs (default 1M is too low)
    USE_SPACY = True
    log.info("spacy sentencizer loaded — using robust sentence splitting")
except Exception:
    USE_SPACY = False
    log.info("spacy not available — using regex sentence splitter (install spacy for better results)")

# ── Configuration ─────────────────────────────────────────────────────────────

KNOWLEDGE_BASE: dict[str, list[str]] = {
    "aiml": [
        "knowledge_base/aiml/MachineLearningTomMitchell.pdf",
        "knowledge_base/aiml/2019BurkovTheHundred-pageMachineLearning.pdf",
        "knowledge_base/aiml/Bishop-Pattern-Recognition-and-Machine-Learning-2006.pdf",
        "knowledge_base/aiml/Artificial Intelligence, Machine Learning, and Deep Learning.pdf",
    ],
    "datascience": [
        "knowledge_base/datascience/Introduction to Machine Learning with Python ( PDFDrive.com )-min.pdf",
        "knowledge_base/datascience/Master Machine Learning Algorithms - Discover how they work and Implement Them From Scratch by Jason Brownlee (z-lib.org).pdf",
    ],
}

CHROMA_PATH      = "./chroma_db"
BM25_PATH        = "./bm25_indexes"
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"
EMBED_BATCH_SIZE = 64

# Semantic chunking
SIMILARITY_THRESHOLD = 0.25   # adjacent-sentence median is ~0.33 for MiniLM on textbooks; 0.75 cut 99.7% of pairs
MAX_CHUNK_CHARS      = 2000   # hard cap (~500 tokens). prevents runaway chunks
MIN_CHUNK_CHARS      = 120    # discard fragments shorter than this
MIN_CHUNK_SENTENCES  = 2      # a single sentence fragment is never a complete thought

# Heading detection — tuned to actual PDF heading formats observed in our books:
#   Mitchell : "CHAPTER", "1.1 WELL-POSED LEARNING PROBLEMS", "MACHINE LEARNING"
#   Burkov   : "1 Introduction", "1.1 What is Machine Learning"
#   Brownlee : "Chapter 1", "Part I", "1.1 Audience", "6.2 Bias Error"
#   AI/ML/DL : "Chapter 4: Deep Learning Introduction", "What Is an RNN?"
HEADING_REGEXES = [
    r"^(Chapter|CHAPTER)\s+\d+",                         # Chapter 3, CHAPTER
    r"^(Part|PART)\s+[IVXLC\d]+",                        # Part I, Part II, PART 3
    r"^\d+\.\d+(\.\d+)?\s+[A-Z]",                        # 3.1 Gradient Descent
    r"^\d+\s+[A-Z][a-zA-Z\s]{3,50}$",                    # 1 Introduction, 9 Gradient Descent
    r"^[A-Z][A-Z\s&\-]{4,50}$",                          # ALL CAPS headings (MACHINE LEARNING)
    r"^(Introduction|Summary|Conclusion|Abstract|Appendix|Preface|Exercises)\b",
    r"^What (Is|Are)\s+.{5,60}\??",                      # What Is an RNN?, What Are GANs?
    r"^Chapter\s+\d+:\s+",                                # Chapter 4: Deep Learning Introduction
]

# Sections to skip entirely — contain no interview-relevant content
SKIP_SECTIONS = {
    "acknowledgments", "acknowledgements", "references", "bibliography",
    "index", "preface", "about the author", "table of contents",
    "contents", "editorial reviews", "product details",
    "exercises", "appendix",
}

# ── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class Sentence:
    """
    A single sentence extracted from the PDF, carrying its origin metadata.
    This is the atomic unit that flows into cross-page chunking.
    """
    text: str
    page_num: int
    section_title: str


@dataclass
class Chunk:
    """One semantic unit ready for embedding and storage."""
    id: str
    text: str
    source: str
    role: str
    page_num: int        # page of the FIRST sentence in this chunk
    section_title: str   # section of the FIRST sentence in this chunk
    chunk_index: int

    def to_metadata(self) -> dict:
        return {
            "source": self.source,
            "role": self.role,
            "page_num": self.page_num,
            "section_title": self.section_title,
            "chunk_index": self.chunk_index,
        }


# ── Text Cleaning ─────────────────────────────────────────────────────────────

def clean_page_text(raw: str) -> str:
    """
    Remove PDF artifacts from a single page's raw text before sentence splitting.

    Handles:
    - Standalone page numbers (e.g. '— 42 —', '42', '• 42 •')
    - Copyright / footer lines
    - Hyphenated line breaks ('mul-\ntiply' → 'multiply')
    - Soft line breaks within paragraphs (single \n that are not paragraph ends)
    - Excessive whitespace
    """
    lines = raw.split("\n")

    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Drop purely numeric lines (page numbers)
        if re.match(r"^[\-\u2013\u2014\u2022]?\s*\d{1,4}\s*[\-\u2013\u2014\u2022]?$", stripped):
            continue
        # Drop copyright / footer lines
        if re.match(r"^(copyright|©|all rights reserved|\bwww\.\S+)", stripped, re.IGNORECASE):
            continue
        # Drop lines that are only 1–3 characters (stray bullets, chars)
        if len(stripped) <= 3:
            continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Rejoin hyphenated line breaks: 'back-\npropagation' → 'backpropagation'
    text = re.sub(r"-\n\s*", "", text)

    # Collapse soft line breaks (single \n inside a paragraph → space)
    # A real paragraph break is \n\n — preserve those
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    # Collapse runs of whitespace
    text = re.sub(r"[ \t]+", " ", text)

    # Remove form feeds
    text = text.replace("\f", "")

    # Max 2 consecutive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def clean_section_title(raw: str) -> str:
    """
    Collapse a potentially multiline heading into a single readable string.

    Input:  'CHAPTER\nARTIFICIAL\nNEURAL\nNETWORKS'
    Output: 'CHAPTER ARTIFICIAL NEURAL NETWORKS'
    """
    title = " ".join(raw.split())
    # Remove TRAILING page numbers from TOC entries (e.g. 'What Is an RNN? 128' → 'What Is an RNN?')
    # Must NOT strip embedded numbers ('Chapter 6 Bayesian' should keep the 6)
    title = re.sub(r"\s\d{1,4}$", "", title)
    # Remove bullet characters
    title = re.sub(r"[•·▪▸►\u2022]", "", title)
    # Collapse multiple spaces
    title = re.sub(r"\s{2,}", " ", title).strip()
    return title[:80]


# ── Heading Detection ─────────────────────────────────────────────────────────

def _detect_page_heading(raw_text: str) -> str | None:
    """
    Detect the best heading from a page's RAW text (before cleaning).

    Must run on raw text because clean_page_text() collapses single newlines
    into spaces, merging headings into paragraph text. The merged lines exceed
    100 chars and get rejected — that's why everything was tagged 'Introduction'.

    Two-tier priority:
      1. Numbered headings ('1.1 Gradient Descent', 'Chapter 4: DL') — always real
      2. All other patterns (all-caps, keywords) — may include running headers
    Within each tier, the LAST match wins (real headings appear below running headers).
    """
    numbered_heading = None
    other_heading = None

    for line in raw_text.split("\n"):
        stripped = line.strip()
        if not stripped or len(stripped) > 100 or len(stripped) <= 3:
            continue

        # Tier 1: Numbered headings — most reliable, never running headers
        # Chapter regex needs length guard: 'Chapter 6 contains a code sample...'
        # is a sentence, not a heading (78 chars). Real: 'Chapter 4: Deep Learning' (24 chars).
        if (re.match(r"^\d+\.\d+(\.\d+)?\s+[A-Z]", stripped) and len(stripped) < 80 or
            re.match(r"^\d+\s+[A-Z][a-zA-Z\s]{3,50}$", stripped) or
            (re.match(r"^Chapter\s+\d+[:\s]", stripped, re.IGNORECASE) and len(stripped) < 60)):
            numbered_heading = stripped

        # Tier 2: Other heading patterns (keywords, all-caps, question-style)
        # Length cap at 60 — headings are short. Prevents sentences from matching.
        elif len(stripped) < 60 and (
              re.match(r"^(Part|PART)\s+[IVXLC\d]+", stripped) or
              re.match(r"^What (Is|Are)\s+.{5,60}\??", stripped) or
              re.match(r"^(Introduction|Summary|Conclusion|Abstract|Appendix|Exercises)\b", stripped) or
              re.match(r"^[A-Z][A-Z\s&\-]{4,50}$", stripped)):
            other_heading = stripped

    return numbered_heading or other_heading


# ── Sentence Splitting ────────────────────────────────────────────────────────

def split_sentences_spacy(text: str) -> list[str]:
    """Use spacy sentencizer — handles abbreviations and decimals correctly."""
    doc = _nlp(text)
    return [sent.text.strip() for sent in doc.sents if len(sent.text.strip()) > 20]


def split_sentences_regex(text: str) -> list[str]:
    """
    Regex sentence splitter with abbreviation protection.

    Protects before splitting:
        e.g.  i.e.  et al.  Fig.  Eq.  vs.  Dr.  Prof.  No.  Vol.  Sec.
        decimal numbers like 0.75 or 3.14

    Without this, 'The learning rate is 0.75. We found...' would be
    incorrectly split at '0.75'.
    """
    ABBREV_MAP = [
        (r"\be\.g\.",   "__EG__"),
        (r"\bi\.e\.",   "__IE__"),
        (r"\bet al\.",  "__ETAL__"),
        (r"\bFig\.",    "__FIG__"),
        (r"\bEq\.",     "__EQ__"),
        (r"\bvs\.",     "__VS__"),
        (r"\bDr\.",     "__DR__"),
        (r"\bProf\.",   "__PROF__"),
        (r"\bNo\.",     "__NO__"),
        (r"\bVol\.",    "__VOL__"),
        (r"\bSec\.",    "__SEC__"),
        (r"\bAl\.",     "__AL__"),
        (r"(\d)\.(\d)", r"\1__DEC__\2"),   # decimals: 3.14 → 3__DEC__14
    ]

    protected = text
    for pattern, replacement in ABBREV_MAP:
        protected = re.sub(pattern, replacement, protected)

    # Split on sentence-ending punctuation followed by whitespace + capital letter
    raw_parts = re.split(r"(?<=[.?!])\s+(?=[A-Z\"])", protected)

    RESTORE_MAP = {
        "__EG__":   "e.g.",
        "__IE__":   "i.e.",
        "__ETAL__": "et al.",
        "__FIG__":  "Fig.",
        "__EQ__":   "Eq.",
        "__VS__":   "vs.",
        "__DR__":   "Dr.",
        "__PROF__": "Prof.",
        "__NO__":   "No.",
        "__VOL__":  "Vol.",
        "__SEC__":  "Sec.",
        "__AL__":   "Al.",
        "__DEC__":  ".",
    }

    result = []
    for s in raw_parts:
        for placeholder, original in RESTORE_MAP.items():
            s = s.replace(placeholder, original)
        s = s.strip()
        if len(s) > 20:
            result.append(s)

    return result


def split_sentences(text: str) -> list[str]:
    """Route to spacy or regex depending on availability."""
    if USE_SPACY:
        return split_sentences_spacy(text)
    return split_sentences_regex(text)


# ── PDF → Sentence Stream ─────────────────────────────────────────────────────

def extract_sentence_stream(pdf_path: str) -> list[Sentence]:
    """
    Extract the entire PDF as a flat stream of Sentence objects.

    Key design decision:
        Page boundaries are NOT chunking boundaries. Each Sentence carries
        its page_num and section_title as metadata, but chunking happens
        across the full stream — so a topic that spans pages 80–81 ends up
        in the same chunk because its sentences are semantically similar and
        no section boundary separates them.

    Section title is running state — updated when a heading is detected on a
    page, inherited by all following sentences until the next heading.
    """
    sentence_stream: list[Sentence] = []
    current_section = "Introduction"

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        log.info(f"     Total pages: {total}")

        for page_num, page in enumerate(
            tqdm(pdf.pages, desc="  Extracting", leave=False), start=1
        ):
            raw = page.extract_text()
            if not raw:
                continue

            # Detect headings from RAW text (before cleaning destroys line boundaries)
            detected = _detect_page_heading(raw)
            if detected:
                current_section = clean_section_title(detected)

            # Skip junk sections (acknowledgments, references, etc.)
            if any(skip in current_section.lower() for skip in SKIP_SECTIONS):
                continue

            cleaned = clean_page_text(raw)
            if not cleaned:
                continue

            # Sentence-split this page and add to stream
            for sent_text in split_sentences(cleaned):
                sentence_stream.append(Sentence(
                    text=sent_text,
                    page_num=page_num,
                    section_title=current_section,
                ))

    log.info(f"     Sentences extracted: {len(sentence_stream)}")
    return sentence_stream


# ── Cross-Page Semantic Chunking ──────────────────────────────────────────────

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D numpy vectors."""
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def semantic_chunk_stream(
    sentences: list[Sentence],
    model: SentenceTransformer,
    source: str,
    role: str,
) -> list[Chunk]:
    """
    Semantic chunking over the FULL document sentence stream (not per-page).

    Cut a new chunk when ANY of these is true:
      a) cosine_similarity(sentence[i-1], sentence[i]) < SIMILARITY_THRESHOLD
         → topic boundary detected by embedding similarity drop
      b) accumulated chars > MAX_CHUNK_CHARS
         → hard size cap to prevent runaway chunks
      c) sentence[i].section_title != sentence[i-1].section_title
         → explicit section boundary: never merge across sections

    Each chunk inherits page_num and section_title from its FIRST sentence.

    Cross-page example:
        Page 80, section "Gradient Descent": sentences A B C
        Page 81, section "Gradient Descent": sentences D E F
        → A B C D E F all have high mutual similarity and same section
        → they end up in ONE chunk spanning both pages
        → this would have been impossible with per-page chunking
    """
    if not sentences:
        return []

    texts = [s.text for s in sentences]

    # Embed all sentences in batches (one pass — efficient)
    log.info(f"     Embedding {len(sentences)} sentences...")
    all_embeddings = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        vecs = model.encode(batch, convert_to_numpy=True, show_progress_bar=False)
        all_embeddings.extend(vecs)
    embeddings = np.array(all_embeddings)

    # Chunking pass
    chunks: list[Chunk] = []
    chunk_index = 0
    current_group: list[Sentence] = [sentences[0]]
    current_chars = len(sentences[0].text)

    for i in range(1, len(sentences)):
        sim             = cosine_similarity(embeddings[i - 1], embeddings[i])
        section_changed = sentences[i].section_title != sentences[i - 1].section_title
        over_cap        = current_chars > MAX_CHUNK_CHARS

        should_cut = (sim < SIMILARITY_THRESHOLD) or section_changed or over_cap

        if should_cut:
            chunk = _build_chunk(current_group, source, role, chunk_index)
            if chunk:
                chunks.append(chunk)
                chunk_index += 1
            current_group = [sentences[i]]
            current_chars = len(sentences[i].text)
        else:
            current_group.append(sentences[i])
            current_chars += len(sentences[i].text)

    # Flush last group
    chunk = _build_chunk(current_group, source, role, chunk_index)
    if chunk:
        chunks.append(chunk)

    return chunks


def _build_chunk(
    group: list[Sentence],
    source: str,
    role: str,
    chunk_index: int,
) -> Chunk | None:
    """
    Assemble a Chunk from a sentence group.
    Returns None if the text is too short to be meaningful.
    Metadata (page_num, section_title) taken from the FIRST sentence.
    """
    text = " ".join(s.text for s in group).strip()
    if len(text) < MIN_CHUNK_CHARS or len(group) < MIN_CHUNK_SENTENCES:
        return None

    return Chunk(
        id=str(uuid.uuid4()),
        text=text,
        source=source,
        role=role,
        page_num=group[0].page_num,
        section_title=group[0].section_title,
        chunk_index=chunk_index,
    )


def fallback_chunk(
    sentences: list[Sentence],
    source: str,
    role: str,
) -> list[Chunk]:
    """
    RecursiveCharacterTextSplitter fallback for when semantic chunking
    produces nothing (e.g. a page that's all equations or tables).
    """
    if not sentences:
        return []

    full_text    = " ".join(s.text for s in sentences)
    first_page   = sentences[0].page_num
    first_section = sentences[0].section_title

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=MAX_CHUNK_CHARS,
        chunk_overlap=200,
        length_function=len,
    )
    return [
        Chunk(
            id=str(uuid.uuid4()),
            text=t.strip(),
            source=source,
            role=role,
            page_num=first_page,
            section_title=first_section,
            chunk_index=i,
        )
        for i, t in enumerate(splitter.split_text(full_text))
        if len(t.strip()) >= MIN_CHUNK_CHARS
    ]


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_chunks(chunks: list[Chunk], model: SentenceTransformer) -> list[list[float]]:
    """Embed all chunk texts in batches. Returns list of embedding vectors."""
    texts = [c.text for c in chunks]
    all_embeddings: list[list[float]] = []

    for i in tqdm(range(0, len(texts), EMBED_BATCH_SIZE), desc="  Embedding chunks", leave=False):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        vecs  = model.encode(batch, convert_to_numpy=True)
        all_embeddings.extend(vecs.tolist())

    return all_embeddings


# ── ChromaDB Storage ──────────────────────────────────────────────────────────

def upsert_to_chroma(
    chunks: list[Chunk],
    embeddings: list[list[float]],
    collection: chromadb.Collection,
) -> None:
    """Upsert chunks + embeddings into ChromaDB in safe batch sizes."""
    BATCH = 500
    for i in range(0, len(chunks), BATCH):
        collection.upsert(
            ids       =[c.id for c in chunks[i : i + BATCH]],
            embeddings=embeddings[i : i + BATCH],
            documents =[c.text for c in chunks[i : i + BATCH]],
            metadatas =[c.to_metadata() for c in chunks[i : i + BATCH]],
        )
    log.info(f"    Upserted {len(chunks)} chunks → '{collection.name}'")


# ── BM25 Index ────────────────────────────────────────────────────────────────

def build_bm25_index(chunks: list[Chunk], role: str) -> None:
    """
    Build and pickle a BM25Okapi index over all chunks for a role.

    Stored alongside parallel chunk_ids / chunk_texts / chunk_metadatas so
    the retriever can map BM25 result indices back to full chunk data without
    re-querying ChromaDB.
    """
    os.makedirs(BM25_PATH, exist_ok=True)

    tokenised = [re.findall(r"[a-z0-9]+", c.text.lower()) for c in chunks]
    bm25      = BM25Okapi(tokenised)

    payload = {
        "bm25":            bm25,
        "chunk_ids":       [c.id for c in chunks],
        "chunk_texts":     [c.text for c in chunks],
        "chunk_metadatas": [c.to_metadata() for c in chunks],
    }

    path = os.path.join(BM25_PATH, f"{role}_bm25.pkl")
    with open(path, "wb") as f:
        pickle.dump(payload, f)

    log.info(f"    BM25 index → {path}  ({len(chunks)} entries)")


# ── Per-PDF Orchestration ─────────────────────────────────────────────────────

def ingest_pdf(
    pdf_path: str,
    role: str,
    collection: chromadb.Collection,
    model: SentenceTransformer,
) -> list[Chunk]:
    """
    Full pipeline for one PDF:
        PDF → sentence stream → semantic chunks → embeddings → ChromaDB
    Returns Chunk list so the caller can build the BM25 index after all PDFs.
    """
    if not os.path.exists(pdf_path):
        log.warning(f"  Skipping (not found): {pdf_path}")
        return []

    log.info(f"\n  📄 {os.path.basename(pdf_path)}")

    sentences = extract_sentence_stream(pdf_path)
    if not sentences:
        log.warning("     No text extracted — skipping.")
        return []

    chunks = semantic_chunk_stream(sentences, model, source=pdf_path, role=role)
    log.info(f"     Chunks (semantic): {len(chunks)}")

    if not chunks:
        log.warning("     Semantic chunking returned 0 — using fallback.")
        chunks = fallback_chunk(sentences, source=pdf_path, role=role)
        log.info(f"     Chunks (fallback): {len(chunks)}")

    if not chunks:
        log.warning("     No chunks produced — skipping.")
        return []

    embeddings = embed_chunks(chunks, model)
    upsert_to_chroma(chunks, embeddings, collection)
    return chunks


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("Knowledge Base Ingestion — Upgraded Pipeline")
    log.info("  Chunking : Cross-page semantic (full document sentence stream)")
    log.info(f"  Sentences: {'spacy sentencizer' if USE_SPACY else 'protected regex splitter'}")
    log.info("  Storage  : ChromaDB (dense) + BM25 pickle (sparse)")
    log.info("=" * 60)

    log.info(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    grand_total = 0

    for role, pdf_paths in KNOWLEDGE_BASE.items():
        log.info(f"\n{'─' * 50}")
        log.info(f"Role: {role.upper()}")

        collection_name = f"{role}_knowledge"
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(f"Collection '{collection_name}' — existing: {collection.count()} chunks")

        role_chunks: list[Chunk] = []
        for pdf_path in pdf_paths:
            chunks = ingest_pdf(pdf_path, role, collection, model)
            role_chunks.extend(chunks)

        if role_chunks:
            log.info(f"\n  Building BM25 index for '{role}'...")
            build_bm25_index(role_chunks, role)

        final_count = collection.count()
        log.info(f"  '{collection_name}' total: {final_count} chunks")
        grand_total += final_count

    log.info(f"\n{'=' * 60}")
    log.info(f"✅ Ingestion complete — {grand_total} total chunks")
    log.info(f"   ChromaDB → {CHROMA_PATH}/")
    log.info(f"   BM25     → {BM25_PATH}/")
    log.info("=" * 60)


if __name__ == "__main__":
    main()