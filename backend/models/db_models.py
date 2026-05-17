"""
db_models.py — SQLAlchemy ORM Models
=====================================
All database tables for the interview system.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, JSON
from database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    """An interview session — one per candidate attempt."""
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    role = Column(String, nullable=False)  # 'aiml' or 'datascience'
    status = Column(String, default="created")
    # Status flow: created → resume_uploaded → interview_started → interview_completed → summarized
    resume_text = Column(Text, nullable=True)
    parsed_resume = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class Question(Base):
    """A generated interview question belonging to a session."""
    __tablename__ = "questions"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    question_index = Column(Integer, nullable=False)  # 0-based order
    question_text = Column(Text, nullable=False)
    topic = Column(String, nullable=False)
    difficulty = Column(String, default="mid")
    source_concept = Column(String, nullable=True)
    context_chunks = Column(JSON, nullable=True)  # list of chunk IDs for traceability
    created_at = Column(DateTime, default=utc_now)


class Answer(Base):
    """A candidate's answer to a specific question."""
    __tablename__ = "answers"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    question_id = Column(String, ForeignKey("questions.id"), nullable=False)
    answer_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)


class Summary(Base):
    """LLM-generated interview summary and assessment."""
    __tablename__ = "summaries"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, unique=True)
    overall_score = Column(Float, nullable=True)
    strengths = Column(JSON, nullable=True)       # list of strings
    gaps = Column(JSON, nullable=True)             # list of strings
    per_question = Column(JSON, nullable=True)     # list of assessment dicts
    recommendations = Column(JSON, nullable=True)  # list of strings
    created_at = Column(DateTime, default=utc_now)
