"""
resume.py — Resume Upload Router
==================================
POST /api/v1/sessions/{id}/resume → upload PDF, parse, update session
"""

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.db_models import Session
from models.schemas import ResumeUploadResponse
from services.resume_service import extract_text_from_pdf, parse_resume_with_llm
from config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/sessions", tags=["resume"])


@router.post("/{session_id}/resume", response_model=ResumeUploadResponse)
async def upload_resume(
    session_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF resume, extract text, parse with LLM, update session."""

    # Validate session exists
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted")

    # Validate file size
    contents = await file.read()
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=422,
            detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB",
        )

    # Extract text from PDF
    log.info(f"Extracting text from resume: {file.filename}")
    resume_text = await asyncio.to_thread(extract_text_from_pdf, contents)

    if not resume_text or len(resume_text.strip()) < 50:
        raise HTTPException(
            status_code=422,
            detail="Could not extract meaningful text from the PDF. "
                   "Please ensure it's a text-based PDF (not a scanned image).",
        )

    # Parse resume with LLM
    log.info("Parsing resume with LLM...")
    parsed_resume = await asyncio.to_thread(parse_resume_with_llm, resume_text)

    # Update session
    session.resume_text = resume_text
    session.parsed_resume = parsed_resume
    session.status = "resume_uploaded"

    await db.flush()

    return ResumeUploadResponse(
        session_id=session_id,
        parsed_resume=parsed_resume,
        status="resume_uploaded",
    )
