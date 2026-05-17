"""
sessions.py — Session Router
==============================
POST /api/v1/sessions       → create a new interview session
GET  /api/v1/sessions/{id}  → get session details
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.db_models import Session
from models.schemas import SessionCreate, SessionResponse

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

VALID_ROLES = {"aiml", "datascience"}


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    """Create a new interview session for a given role."""
    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid role '{body.role}'. Must be one of: {VALID_ROLES}",
        )

    session = Session(role=body.role)
    db.add(session)
    await db.flush()
    await db.refresh(session)

    return session


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get session details by ID."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return session
