"""NEXUS User Sessions API Endpoints

Provides session isolation, tracking, and metadata management across
Dashboard and Ambient desktop surfaces.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    SessionModel,
    UserModel,
    generate_uuid,
)
from packages.types.nexus_types.schemas import (
    SessionCreateRequest,
    SessionResponse,
)
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.database import get_db

logger = get_logger("nexus.sessions")
sessions_router = APIRouter(prefix="/sessions", tags=["sessions"])


def _format_session(model: SessionModel) -> SessionResponse:
    return SessionResponse(
        session_id=str(model.id),
        user_id=str(model.user_id),
        title=str(model.title or "Session"),
        metadata=dict(model.os_context or {}),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@sessions_router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    req: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> SessionResponse:
    """Create a new session record for the authenticated user."""
    sess_id = generate_uuid("sess")
    now = datetime.now(UTC)
    session = SessionModel(
        id=sess_id,
        user_id=current_user.id,
        surface="dashboard",
        title=req.title,
        os_context=req.metadata,
        created_at=now,
        updated_at=now,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info("session_created", session_id=session.id, user_id=current_user.id)
    return _format_session(session)


@sessions_router.get("", response_model=list[SessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> list[SessionResponse]:
    """List all sessions belonging to the authenticated user."""
    res = await db.execute(
        select(SessionModel)
        .where(SessionModel.user_id == current_user.id)
        .order_by(desc(SessionModel.updated_at))
    )
    sessions = res.scalars().all()
    return [_format_session(s) for s in sessions]


@sessions_router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> SessionResponse:
    """Get details of a specific session with tenant isolation."""
    res = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.user_id == current_user.id,
        )
    )
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )
    return _format_session(session)


@sessions_router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> None:
    """Delete a session and all cascading task DAGs."""
    res = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.user_id == current_user.id,
        )
    )
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )
    await db.delete(session)
    await db.commit()
    logger.info("session_deleted", session_id=session_id, user_id=current_user.id)
