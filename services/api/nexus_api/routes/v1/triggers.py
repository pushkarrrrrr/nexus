"""FastAPI routes for Proactive Watchers, Triggers, and Self-Healing Telemetry."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    ProactiveTriggerModel,
    TriggerEventModel,
    UserModel,
)
from packages.shared.nexus_shared.proactive import (
    SystemMetricsSnapshot,
    TriggerCreateRequest,
    TriggerEvaluationResult,
    TriggerEventResponse,
    TriggerResponse,
    get_proactive_engine,
    get_system_watcher,
)
from services.api.nexus_api.auth.dependencies import (
    get_current_user,
    get_optional_current_user,
)
from services.api.nexus_api.database import get_db

logger = get_logger("nexus.routes.triggers")

triggers_router = APIRouter(prefix="/triggers", tags=["Proactive Triggers"])
watchers_router = APIRouter(prefix="/watchers", tags=["System Watchers"])


# ---------------------------------------------------------------------------
# Watcher Telemetry Endpoints
# ---------------------------------------------------------------------------
@watchers_router.get("/metrics", response_model=SystemMetricsSnapshot)
async def get_system_metrics(
    _user: UserModel | None = Depends(get_optional_current_user),
) -> SystemMetricsSnapshot:
    """Return live host telemetry and health metrics."""
    watcher = get_system_watcher()
    return watcher.capture_metrics()


# ---------------------------------------------------------------------------
# Trigger Management Endpoints
# ---------------------------------------------------------------------------
@triggers_router.get("", response_model=list[TriggerResponse])
async def list_triggers(
    user: UserModel | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TriggerResponse]:
    """List all proactive triggers defined for current user or local instance."""
    stmt = select(ProactiveTriggerModel).order_by(desc(ProactiveTriggerModel.created_at))
    if user:
        stmt = stmt.where(ProactiveTriggerModel.user_id == user.id)
    result = await db.execute(stmt)
    triggers = list(result.scalars().all())

    return [
        TriggerResponse(
            id=t.id,
            user_id=t.user_id,
            name=t.name,
            trigger_type=t.trigger_type,  # type: ignore[arg-type]
            condition=t.condition,
            action_capability=t.action_capability,
            action_params=t.action_params,
            is_active=t.is_active,
            cooldown_seconds=t.cooldown_seconds,
            last_triggered_at=t.last_triggered_at,
            trigger_count=t.trigger_count,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in triggers
    ]


@triggers_router.post("", response_model=TriggerResponse, status_code=status.HTTP_201_CREATED)
async def create_trigger(
    request: TriggerCreateRequest,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TriggerResponse:
    """Create a new proactive trigger rule."""
    trigger = ProactiveTriggerModel(
        user_id=user.id,
        name=request.name,
        trigger_type=request.trigger_type,
        condition=request.condition.model_dump(),
        action_capability=request.action_capability,
        action_params=request.action_params,
        is_active=request.is_active,
        cooldown_seconds=request.cooldown_seconds,
    )
    db.add(trigger)
    await db.commit()
    await db.refresh(trigger)

    logger.info("proactive_trigger_created", trigger_id=trigger.id, name=trigger.name)

    return TriggerResponse(
        id=trigger.id,
        user_id=trigger.user_id,
        name=trigger.name,
        trigger_type=trigger.trigger_type,  # type: ignore[arg-type]
        condition=trigger.condition,
        action_capability=trigger.action_capability,
        action_params=trigger.action_params,
        is_active=trigger.is_active,
        cooldown_seconds=trigger.cooldown_seconds,
        last_triggered_at=trigger.last_triggered_at,
        trigger_count=trigger.trigger_count,
        created_at=trigger.created_at,
        updated_at=trigger.updated_at,
    )


@triggers_router.get("/events", response_model=list[TriggerEventResponse])
async def list_trigger_events(
    limit: int = Query(default=50, ge=1, le=200),
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TriggerEventResponse]:
    """List execution history and anomaly detections."""
    stmt = (
        select(TriggerEventModel)
        .where(TriggerEventModel.user_id == user.id)
        .order_by(desc(TriggerEventModel.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    events = list(result.scalars().all())

    return [
        TriggerEventResponse(
            id=e.id,
            trigger_id=e.trigger_id,
            user_id=e.user_id,
            event_type=e.event_type,
            observed_data=e.observed_data,
            action_proposed=e.action_proposed,
            approval_id=e.approval_id,
            status=e.status,  # type: ignore[arg-type]
            result_payload=e.result_payload,
            error_message=e.error_message,
            created_at=e.created_at,
        )
        for e in events
    ]


@triggers_router.get("/{trigger_id}", response_model=TriggerResponse)
async def get_trigger(
    trigger_id: str,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TriggerResponse:
    """Retrieve details for a specific trigger."""
    stmt = select(ProactiveTriggerModel).where(
        ProactiveTriggerModel.id == trigger_id,
        ProactiveTriggerModel.user_id == user.id,
    )
    result = await db.execute(stmt)
    trigger = result.scalar_one_or_none()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    return TriggerResponse(
        id=trigger.id,
        user_id=trigger.user_id,
        name=trigger.name,
        trigger_type=trigger.trigger_type,  # type: ignore[arg-type]
        condition=trigger.condition,
        action_capability=trigger.action_capability,
        action_params=trigger.action_params,
        is_active=trigger.is_active,
        cooldown_seconds=trigger.cooldown_seconds,
        last_triggered_at=trigger.last_triggered_at,
        trigger_count=trigger.trigger_count,
        created_at=trigger.created_at,
        updated_at=trigger.updated_at,
    )


@triggers_router.patch("/{trigger_id}/toggle", response_model=TriggerResponse)
async def toggle_trigger(
    trigger_id: str,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TriggerResponse:
    """Toggle activation state of a trigger."""
    stmt = select(ProactiveTriggerModel).where(
        ProactiveTriggerModel.id == trigger_id,
        ProactiveTriggerModel.user_id == user.id,
    )
    result = await db.execute(stmt)
    trigger = result.scalar_one_or_none()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    trigger.is_active = not trigger.is_active
    await db.commit()
    await db.refresh(trigger)

    return TriggerResponse(
        id=trigger.id,
        user_id=trigger.user_id,
        name=trigger.name,
        trigger_type=trigger.trigger_type,  # type: ignore[arg-type]
        condition=trigger.condition,
        action_capability=trigger.action_capability,
        action_params=trigger.action_params,
        is_active=trigger.is_active,
        cooldown_seconds=trigger.cooldown_seconds,
        last_triggered_at=trigger.last_triggered_at,
        trigger_count=trigger.trigger_count,
        created_at=trigger.created_at,
        updated_at=trigger.updated_at,
    )


@triggers_router.delete("/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(
    trigger_id: str,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a trigger rule."""
    stmt = select(ProactiveTriggerModel).where(
        ProactiveTriggerModel.id == trigger_id,
        ProactiveTriggerModel.user_id == user.id,
    )
    result = await db.execute(stmt)
    trigger = result.scalar_one_or_none()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    await db.delete(trigger)
    await db.commit()


@triggers_router.post("/evaluate", response_model=list[TriggerEvaluationResult])
async def evaluate_triggers_on_demand(
    trigger_id: str | None = None,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TriggerEvaluationResult]:
    """Manually evaluate triggers on demand."""
    engine = get_proactive_engine()
    if trigger_id:
        single_res = await engine.evaluate_single_trigger(db, trigger_id)
        return [single_res] if single_res else []
    return await engine.evaluate_all(db)
