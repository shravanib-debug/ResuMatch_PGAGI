"""
schemas.py — Pydantic Schemas for API Request/Response
=======================================================
Defines all input/output shapes for FastAPI endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Session ───────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    """Request body for creating a new interview session."""
    role: str = Field(..., description="Interview role: 'aiml' or 'datascience'")


class SessionResponse(BaseModel):
    """Response for session endpoints."""
    id: str
    role: str
    status: str
    parsed_resume: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Resume ────────────────────────────────────────────────────────────────────

class ResumeUploadResponse(BaseModel):
    """Response after uploading and parsing a resume."""
    session_id: str
    parsed_resume: dict
    status: str


# ── Questions ─────────────────────────────────────────────────────────────────

class QuestionResponse(BaseModel):
    """A single interview question (no answer leaked)."""
    id: str
    question_index: int
    question_text: str
    topic: str
    difficulty: str

    class Config:
        from_attributes = True


class QuestionsListResponse(BaseModel):
    """All questions for a session."""
    session_id: str
    total_questions: int
    questions: list[QuestionResponse]


# ── Answers ───────────────────────────────────────────────────────────────────

class AnswerCreate(BaseModel):
    """Request body for submitting an answer."""
    question_id: str
    answer_text: str = Field(..., min_length=1)


class AnswerResponse(BaseModel):
    """Response after submitting an answer."""
    id: str
    question_id: str
    answer_text: str
    next_question_index: Optional[int] = None  # None if this was the last question
    is_complete: bool = False  # True when all questions answered

    class Config:
        from_attributes = True


# ── Summary ───────────────────────────────────────────────────────────────────

class PerQuestionAssessment(BaseModel):
    """Assessment for a single Q&A pair."""
    question_text: str
    answer_text: str
    assessment: str  # 'strong', 'adequate', 'weak'
    score: float
    feedback: str
    what_was_missed: str


class SummaryResponse(BaseModel):
    """Full interview summary."""
    session_id: str
    overall_score: float
    strengths: list[str]
    gaps: list[str]
    per_question: list[PerQuestionAssessment]
    recommendations: list[str]

    class Config:
        from_attributes = True


# ── Errors ────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error envelope."""
    detail: str
    error_code: Optional[str] = None
