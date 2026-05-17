# ResuMatch — AI-Powered Candidate Screening System

![Project Architecture](https://img.shields.io/badge/Architecture-Advanced_Hybrid_RAG-blue)
![Backend](https://img.shields.io/badge/Backend-FastAPI-green)
![Frontend](https://img.shields.io/badge/Frontend-Next.js-black)

## 1. What This Project Is

ResuMatch simulates a technical interview. A candidate uploads their resume, selects a target role, and the system generates a personalized set of interview questions grounded in real ML textbooks—not generic prompts pulled from an LLM's latent space.

The questions are specific to what that candidate has claimed on their resume. If someone lists PyTorch, the system retrieves chapters on backpropagation and asks about gradient computation. If they list scikit-learn, it goes to decision tree splitting criteria. The summary page then evaluates their answers and shows where they were strong and where they fell short.

The core challenge this project solves is **grounding**: making sure every question comes from a real source (a textbook chapter) rather than from the LLM's general knowledge, which can hallucinate or ask questions that are too easy, too vague, or off-topic.

---

## 2. System Architecture

### 2.1 The Three Layers

| Layer | Technology | Why this choice |
| --- | --- | --- |
| **Frontend** | Next.js + Tailwind CSS | App Router allows server components, reducing client-side JS. Tailwind keeps styling fast to write. |
| **Backend API** | FastAPI + Pydantic | Native async handles long LLM calls without blocking. Pydantic enforces structured JSON from the LLM—critical for parsing reliability. |
| **Database** | SQLite via aiosqlite + SQLAlchemy | Zero-dependency for local development. SQLAlchemy means switching to PostgreSQL in production is a one-line config change. |
| **Vector Store** | ChromaDB (persistent) | Local, no-server-required vector DB. Persists embeddings to disk so ingestion only runs once. |
| **Keyword Index** | BM25 (rank-bm25) | Parallel sparse index over the same chunks. Catches exact technical terms that semantic search misses. |

### 2.2 The Stateless API Design
The backend is fully stateless. Every request carries a `session_id` (UUID). No session data lives in memory on the server—it all goes to SQLite immediately. This means if the server restarts mid-interview, no candidate data is lost. It also means the backend could be replicated horizontally without any sticky-session configuration.

### 2.3 Service Layer Pattern
FastAPI routers contain no business logic—they receive a request, validate it, and immediately delegate to a service singleton (`rag_service`, `resume_service`, `summary_service`). This allows the RAG pipeline to be unit tested completely independently of HTTP requests.

---

## 3. The AI/ML Pipeline: Advanced Hybrid RAG

This is the core of the project. A plain RAG pipeline (embed query → cosine similarity → top-k chunks → LLM) was explicitly rejected as insufficient for this use case. 

### Pipeline Flow
`Resume + Role` → `[1] Query Construction` → `[2] Semantic Search (ChromaDB)` → `[3] BM25 Keyword Search` → `[4] Score Fusion (60/40)` → `[5] Cross-Encoder Reranking` → `[6] Batch LLM Generation`

#### Step 1: Knowledge Ingestion (Cross-Page Semantic Chunking)
Before the system can answer any questions, the textbooks need to be broken into retrievable pieces. Most RAG tutorials use fixed-size character splits that cut paragraphs in half. 
*   **What was built:** The ingestion script extracts text using `pdfplumber` and builds a flat stream of sentences across the entire document. Page boundaries become metadata, not chunking boundaries. 
*   **Why:** If an explanation of gradient descent crosses a page boundary, fixed-size chunking cuts it in half. Semantic chunking keeps topics coherent.

#### Step 2: Dual Indexing & Retrieval
Every chunk is stored in two places: **ChromaDB** (semantic search) and a **BM25 index** (keyword matching). 
*   **Why hybrid:** If a candidate lists 'softmax' on their resume, semantic search might return chunks about activation functions generally. BM25 returns chunks explicitly containing the word 'softmax'. Both signals are fused (60% semantic, 40% BM25).

#### Step 3: Cross-Encoder Reranking
The initial retrieval uses bi-encoders. This is fast but imprecise. The cross-encoder (`ms-marco-MiniLM-L-6-v2`) sees the query and each chunk together in one forward pass through a transformer. It produces a much more accurate relevance score because it can attend across both texts simultaneously. 

#### Step 4: Question Generation (Single Batch Call)
A naive implementation would call the LLM five times sequentially to generate five questions, causing high latency (5x API round-trip) and rate-limit risks.
Instead, the prompt is engineered to force the LLM to ingest all retrieved context and output a structured JSON array of **exactly five questions in a single API call**. 

---

## 4. Fallbacks & Graceful Degradation

A system that crashes when an LLM API returns a `429 Too Many Requests` is not production-ready.

| Component | Failure Mode | What the system does instead |
| --- | --- | --- |
| **Resume Parser** | LLM returns malformed JSON | Falls back to regex keyword extraction against a skill dictionary. |
| **Query Constructor** | LLM API rate limit | Heuristic fallback builds queries directly from resume skills. Saves an API call. |
| **Retriever** | ChromaDB collection empty | Returns clear 503 with message: ingestion script has not been run. |

---

## 5. Frontend Design Decisions

*   **State Management with `useReducer`:** The interview flow has multiple states (upload, loading, questions, summary). Using individual `useState` calls leads to race conditions. A `useReducer` hook manages the full state machine explicitly.
*   **Loading State Design:** Question generation takes 10–20 seconds. A blank screen causes panic. The loading state shows a staged progress indicator with dynamic messages ('Analysing your resume' → 'Searching knowledge base' → 'Generating questions').
*   **No Answer Editing After Submission:** Once an answer is submitted, it cannot be edited, mirroring a real technical interview. 

---

## 6. What Makes This Different From a Basic RAG Wrapper?

| Stage | Basic RAG Tutorial | This System |
| --- | --- | --- |
| **Chunking** | Fixed 500-token splits. Cuts mid-sentence. | Cross-page semantic chunking. Cuts where the topic actually changes. |
| **Retrieval** | Single semantic search (cosine distance). | Hybrid: Semantic + BM25, merged with weighted 60/40 scoring. |
| **Ranking** | Raw cosine distance. | Cross-encoder reranking. Query and chunk evaluated together by a transformer. |
| **Generation** | One LLM call per question (High latency). | Single batch call returns structured JSON array of 5 questions. |
| **Failure** | System crashes or returns raw 500 error. | Multiple fallback layers (heuristic extraction and rule-based queries). |

---

## 7. Honest Limitations

No system is perfect. For a true production deployment, the following changes would be prioritized:
*   **Embedding speed:** The embedding model (`all-MiniLM-L6-v2`) runs on CPU. On a machine with a GPU, inference would be 10–20x faster. 
*   **Database concurrency:** SQLite is single-writer. For a production system handling concurrent interviews, this would be swapped to PostgreSQL (SQLAlchemy makes this a one-line configuration change).
*   **PDF heading detection:** Heading detection in `pdfplumber` relies on regex and font-size heuristics. Highly unusual PDF layouts occasionally cause chunks to inherit the wrong section title.

---
*Developed as part of the PGAGI AI/ML & Backend Assignment.*
