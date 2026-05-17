"""
interview.py — Interview Router
=================================
POST /api/v1/sessions/{id}/start                → generate questions via RAG
GET  /api/v1/sessions/{id}/questions            → list all questions
GET  /api/v1/sessions/{id}/questions/{index}    → get single question by index
POST /api/v1/sessions/{id}/answers              → submit an answer
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database import get_db
from models.db_models import Session, Question, Answer
from models.schemas import (
    QuestionResponse,
    QuestionsListResponse,
    AnswerCreate,
    AnswerResponse,
)
from services.rag_service import generate_questions_for_session
from config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/sessions", tags=["interview"])


# ── Start Interview (Generate Questions) ─────────────────────────────────────

@router.post("/{session_id}/start", response_model=QuestionsListResponse)
async def start_interview(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Trigger the RAG pipeline to generate interview questions.
    Requires resume to be uploaded first.
    """
    # Load session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in ("resume_uploaded", "interview_started"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start interview in status '{session.status}'. "
                   "Upload a resume first.",
        )

    # Check if questions already exist (idempotent)
    existing = await db.execute(
        select(Question).where(Question.session_id == session_id)
    )
    if existing.scalars().first():
        # Questions already generated — return them
        return await _get_questions_response(session_id, db)

    if not session.parsed_resume:
        raise HTTPException(
            status_code=400,
            detail="No parsed resume data. Upload a resume first.",
        )

    # Generate questions via RAG pipeline
    log.info(f"Starting interview for session {session_id}, role={session.role}")
    question_dicts = generate_questions_for_session(
        parsed_resume=session.parsed_resume,
        role=session.role,
        num_questions=settings.max_questions_per_session,
    )

    # Store questions in DB
    for idx, q_dict in enumerate(question_dicts):
        question = Question(
            session_id=session_id,
            question_index=idx,
            question_text=q_dict["question_text"],
            topic=q_dict["topic"],
            difficulty=q_dict["difficulty"],
            source_concept=q_dict["source_concept"],
            context_chunks=q_dict.get("source_chunks", []),
        )
        db.add(question)

    session.status = "interview_started"
    await db.flush()

    log.info(f"Generated {len(question_dicts)} questions for session {session_id}")
    return await _get_questions_response(session_id, db)


# ── Get All Questions ─────────────────────────────────────────────────────────

@router.get("/{session_id}/questions", response_model=QuestionsListResponse)
async def get_questions(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get all questions for a session."""
    return await _get_questions_response(session_id, db)


# ── Get Single Question ──────────────────────────────────────────────────────

@router.get("/{session_id}/questions/{index}", response_model=QuestionResponse)
async def get_question_by_index(
    session_id: str,
    index: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single question by its index (0-based)."""
    result = await db.execute(
        select(Question).where(
            Question.session_id == session_id,
            Question.question_index == index,
        )
    )
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=404,
            detail=f"Question at index {index} not found for session '{session_id}'",
        )

    return question


# ── Submit Answer ─────────────────────────────────────────────────────────────

@router.post("/{session_id}/answers", response_model=AnswerResponse)
async def submit_answer(
    session_id: str,
    body: AnswerCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit an answer to a question. Returns next question index."""

    # Validate session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate question exists and belongs to this session
    result = await db.execute(
        select(Question).where(
            Question.id == body.question_id,
            Question.session_id == session_id,
        )
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found in this session")

    # Check if already answered
    result = await db.execute(
        select(Answer).where(Answer.question_id == body.question_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="This question has already been answered")

    # Store answer
    answer = Answer(
        session_id=session_id,
        question_id=body.question_id,
        answer_text=body.answer_text,
    )
    db.add(answer)
    await db.flush()
    await db.refresh(answer)

    # Determine next question
    total_questions = await db.scalar(
        select(func.count(Question.id)).where(Question.session_id == session_id)
    )
    total_answers = await db.scalar(
        select(func.count(Answer.id)).where(Answer.session_id == session_id)
    )

    is_complete = total_answers >= total_questions
    next_index = question.question_index + 1 if not is_complete else None

    if is_complete:
        session.status = "interview_completed"
        await db.flush()

    return AnswerResponse(
        id=answer.id,
        question_id=answer.question_id,
        answer_text=answer.answer_text,
        next_question_index=next_index,
        is_complete=is_complete,
    )


# ── Get Progress (for resume-on-refresh) ─────────────────────────────────────

@router.get("/{session_id}/progress")
async def get_progress(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get the current progress — how many questions answered, answered question IDs."""
    total_questions = await db.scalar(
        select(func.count(Question.id)).where(Question.session_id == session_id)
    )
    # Get all answered question IDs
    result = await db.execute(
        select(Answer.question_id).where(Answer.session_id == session_id)
    )
    answered_ids = [row[0] for row in result.all()]

    return {
        "total_questions": total_questions or 0,
        "answers_submitted": len(answered_ids),
        "answered_question_ids": answered_ids,
        "is_complete": len(answered_ids) >= (total_questions or 0),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_questions_response(
    session_id: str,
    db: AsyncSession,
) -> QuestionsListResponse:
    """Build the questions list response."""
    result = await db.execute(
        select(Question)
        .where(Question.session_id == session_id)
        .order_by(Question.question_index)
    )
    questions = result.scalars().all()

    return QuestionsListResponse(
        session_id=session_id,
        total_questions=len(questions),
        questions=[
            QuestionResponse(
                id=q.id,
                question_index=q.question_index,
                question_text=q.question_text,
                topic=q.topic,
                difficulty=q.difficulty,
            )
            for q in questions
        ],
    )
