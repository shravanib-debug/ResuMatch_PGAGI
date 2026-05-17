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

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import sessions, resume, interview, summary

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
        "http://localhost:3000",    # Next.js dev server
        "http://127.0.0.1:3000",
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
