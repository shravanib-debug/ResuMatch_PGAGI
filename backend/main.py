"""
main.py — FastAPI Application Entry Point
==========================================
AI-Powered Interview System Backend

Start with:
    cd backend
    uvicorn main:app --reload

Docs at: http://localhost:8000/docs
"""

from dotenv import load_dotenv
load_dotenv()  # MUST be before other imports so os.getenv() works in retriever.py

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from database import engine, init_db
from routers import sessions, resume, interview, summary
from services.rag_service import get_retriever

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    log.info("Starting up — creating database tables...")
    await init_db()
    log.info("Database ready.")
    # Load ML models now so the first interview isn't slow and threads can't race the lazy init.
    await asyncio.to_thread(get_retriever)
    yield
    log.info("Shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Interview System",
    description="AI-powered technical interview system with Hybrid Agentic RAG",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip().rstrip("/")
        for origin in get_settings().allowed_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(sessions.router)
app.include_router(resume.router)
app.include_router(interview.router)
app.include_router(summary.router)


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "ai-interview-system"}


@app.get("/ready", tags=["health"])
async def readiness_check():
    """Report whether this instance can serve traffic (load-balancer probe)."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")

    if not list(Path("bm25_indexes").glob("*_bm25.pkl")) or not Path("chroma_db").is_dir():
        raise HTTPException(status_code=503, detail="Indexes missing: run ingest.py")

    return {"status": "ready"}
