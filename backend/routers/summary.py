"""
summary.py — Summary Router
==============================
POST /api/v1/sessions/{id}/summary → generate interview summary
GET  /api/v1/sessions/{id}/summary → get stored summary
"""

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.db_models import Session, Question, Answer, Summary
from models.schemas import SummaryResponse
from services.summary_service import generate_summary

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["summary"])


@router.post("/{session_id}/summary", response_model=SummaryResponse)
async def create_summary(session_id: str, db: AsyncSession = Depends(get_db)):
    """Generate interview summary. Requires all questions to be answered."""

    # Load session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in ("interview_completed", "summarized"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot generate summary in status '{session.status}'. "
                   "Complete all questions first.",
        )

    # Check for existing summary (idempotent)
    result = await db.execute(
        select(Summary).where(Summary.session_id == session_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return _summary_to_response(session_id, existing)

    # Build Q&A pairs
    qa_pairs = await _build_qa_pairs(session_id, db)
    if not qa_pairs:
        raise HTTPException(status_code=400, detail="No answered questions found")

    # Generate summary via LLM
    log.info(f"Generating summary for session {session_id}")
    summary_data = await asyncio.to_thread(
        generate_summary,
        parsed_resume=session.parsed_resume or {},
        role=session.role,
        qa_pairs=qa_pairs,
    )

    # Store in DB
    summary = Summary(
        session_id=session_id,
        overall_score=summary_data.get("overall_score", 5.0),
        strengths=summary_data.get("strengths", []),
        gaps=summary_data.get("gaps", []),
        per_question=summary_data.get("per_question", []),
        recommendations=summary_data.get("recommendations", []),
    )
    db.add(summary)

    session.status = "summarized"
    await db.flush()
    await db.refresh(summary)

    log.info(f"Summary generated: score={summary.overall_score}")
    return _summary_to_response(session_id, summary)


@router.get("/{session_id}/summary", response_model=SummaryResponse)
async def get_summary(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get the stored summary for a session."""
    result = await db.execute(
        select(Summary).where(Summary.session_id == session_id)
    )
    summary = result.scalar_one_or_none()

    if not summary:
        raise HTTPException(
            status_code=404,
            detail="Summary not found. Generate one first via POST.",
        )

    return _summary_to_response(session_id, summary)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _build_qa_pairs(session_id: str, db: AsyncSession) -> list[dict]:
    """Build list of Q&A pair dicts from the database."""
    questions_result = await db.execute(
        select(Question)
        .where(Question.session_id == session_id)
        .order_by(Question.question_index)
    )
    questions = questions_result.scalars().all()

    qa_pairs = []
    for q in questions:
        answer_result = await db.execute(
            select(Answer).where(Answer.question_id == q.id)
        )
        answer = answer_result.scalar_one_or_none()
        if answer:
            qa_pairs.append({
                "question_text": q.question_text,
                "topic": q.topic,
                "answer_text": answer.answer_text,
            })

    return qa_pairs


def _summary_to_response(session_id: str, summary: Summary) -> SummaryResponse:
    """Convert DB model to response schema."""
    return SummaryResponse(
        session_id=session_id,
        overall_score=summary.overall_score or 5.0,
        strengths=summary.strengths or [],
        gaps=summary.gaps or [],
        per_question=summary.per_question or [],
        recommendations=summary.recommendations or [],
    )
