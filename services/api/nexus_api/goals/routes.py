"""NEXUS High-Level Goals & Milestone Management Endpoints

Enables users and orchestrators to define strategic objectives, track
decomposed milestones, and measure autonomous progress over time.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    GoalModel,
    UserModel,
    generate_uuid,
)
from packages.types.nexus_types.schemas import (
    GoalCreateRequest,
    GoalMilestone,
    GoalResponse,
    GoalStatus,
    GoalUpdateRequest,
)
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.database import get_db

logger = get_logger("nexus.goals")
goals_router = APIRouter(prefix="/goals", tags=["goals"])


def _calculate_progress(milestones: list[dict[str, Any]]) -> float:
    if not milestones:
        return 0.0
    completed_count = sum(1 for m in milestones if m.get("completed", False))
    return round((completed_count / len(milestones)) * 100.0, 1)


def _format_goal(model: GoalModel) -> GoalResponse:
    milestones_data = list(model.milestones or [])
    milestones = [
        GoalMilestone(
            id=str(m.get("id", "")),
            title=str(m.get("title", "")),
            completed=bool(m.get("completed", False)),
            completed_at=m.get("completed_at"),
        )
        for m in milestones_data
    ]
    return GoalResponse(
        id=str(model.id),
        user_id=str(model.user_id),
        session_id=str(model.session_id) if model.session_id else None,
        title=str(model.title),
        description=str(model.description) if model.description else None,
        status=GoalStatus(model.status),
        category=str(model.category),
        progress=float(model.progress),
        milestones=milestones,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@goals_router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    req: GoalCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> GoalResponse:
    """Create a new high-level objective with optional milestones."""
    goal_id = generate_uuid("goal")
    now = datetime.now(UTC)

    milestones_dict = [
        {
            "id": m.id or generate_uuid("ms"),
            "title": m.title,
            "completed": m.completed,
            "completed_at": m.completed_at.isoformat() if m.completed_at else None,
        }
        for m in req.milestones
    ]
    initial_progress = _calculate_progress(milestones_dict)

    goal = GoalModel(
        id=goal_id,
        user_id=current_user.id,
        session_id=req.session_id,
        title=req.title,
        description=req.description,
        status=GoalStatus.ACTIVE.value,
        category=req.category or "general",
        progress=initial_progress,
        milestones=milestones_dict,
        created_at=now,
        updated_at=now,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    logger.info("goal_created", goal_id=goal.id, user_id=current_user.id, title=goal.title)
    return _format_goal(goal)


@goals_router.get("", response_model=list[GoalResponse])
async def list_goals(
    status_filter: GoalStatus | None = Query(default=None, alias="status"),
    category_filter: str | None = Query(default=None, alias="category"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> list[GoalResponse]:
    """List all goals belonging to the authenticated user."""
    stmt = (
        select(GoalModel)
        .where(GoalModel.user_id == current_user.id)
        .order_by(desc(GoalModel.updated_at))
    )
    if status_filter:
        stmt = stmt.where(GoalModel.status == status_filter.value)
    if category_filter:
        stmt = stmt.where(GoalModel.category == category_filter)

    res = await db.execute(stmt)
    goals = res.scalars().all()
    return [_format_goal(g) for g in goals]


@goals_router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> GoalResponse:
    """Retrieve details for a specific goal."""
    res = await db.execute(
        select(GoalModel).where(
            GoalModel.id == goal_id,
            GoalModel.user_id == current_user.id,
        )
    )
    goal = res.scalar_one_or_none()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Goal '{goal_id}' not found",
        )
    return _format_goal(goal)


@goals_router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: str,
    req: GoalUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> GoalResponse:
    """Update goal status, title, description, or milestones."""
    res = await db.execute(
        select(GoalModel).where(
            GoalModel.id == goal_id,
            GoalModel.user_id == current_user.id,
        )
    )
    goal = res.scalar_one_or_none()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Goal '{goal_id}' not found",
        )

    now = datetime.now(UTC)
    if req.title is not None:
        goal.title = req.title
    if req.description is not None:
        goal.description = req.description
    if req.status is not None:
        goal.status = req.status.value
    if req.category is not None:
        goal.category = req.category

    if req.milestones is not None:
        milestones_dict = [
            {
                "id": m.id or generate_uuid("ms"),
                "title": m.title,
                "completed": m.completed,
                "completed_at": m.completed_at.isoformat()
                if m.completed_at
                else (now.isoformat() if m.completed else None),
            }
            for m in req.milestones
        ]
        goal.milestones = milestones_dict
        if req.progress is None:
            goal.progress = _calculate_progress(milestones_dict)

    if req.progress is not None:
        goal.progress = float(req.progress)

    # Auto-complete status if progress reached 100% and still marked active
    if goal.progress >= 100.0 and goal.status == GoalStatus.ACTIVE.value:
        goal.status = GoalStatus.COMPLETED.value

    goal.updated_at = now
    await db.commit()
    await db.refresh(goal)
    logger.info("goal_updated", goal_id=goal.id, user_id=current_user.id, status=goal.status)
    return _format_goal(goal)


@goals_router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> None:
    """Delete a goal."""
    res = await db.execute(
        select(GoalModel).where(
            GoalModel.id == goal_id,
            GoalModel.user_id == current_user.id,
        )
    )
    goal = res.scalar_one_or_none()
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Goal '{goal_id}' not found",
        )
    await db.delete(goal)
    await db.commit()
    logger.info("goal_deleted", goal_id=goal_id, user_id=current_user.id)
