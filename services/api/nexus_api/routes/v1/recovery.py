"""REST API routes for Phase 15 Autonomous Self-Correction and Error Recovery."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.agents.recovery import (
    ReplanRecordResponse,
    get_recovery_coordinator,
)
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    ExecutionPlanModel,
    PlanStepModel,
    ReplanRecordModel,
    UserModel,
)
from services.api.nexus_api.auth.dependencies import (
    get_optional_current_user,
)
from services.api.nexus_api.database import get_db

logger = get_logger("nexus.routes.recovery")

recovery_router = APIRouter(prefix="/plans", tags=["Self-Correction & Recovery"])


class DiagnoseStepRequest(BaseModel):
    """Request to manually trigger error reflection and diagnosis for a step."""

    step_id: str = Field(..., description="ID of the failed step to diagnose")
    error_override: str | None = Field(
        default=None, description="Optional custom error message or context override"
    )


class RecoveryStatsResponse(BaseModel):
    """Aggregated statistics for Phase 15 Autonomous Self-Correction & Dynamic Replanning."""

    total_replan_records: int
    resolved_count: int
    rollback_count: int
    hitl_escalation_count: int
    success_rate_percent: float
    strategy_distribution: dict[str, int]
    error_category_distribution: dict[str, int]


@recovery_router.get("/reflections/recent", response_model=list[ReplanRecordResponse])
async def list_recent_reflections(
    limit: int = 50,
    user: UserModel | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReplanRecordResponse]:
    """Retrieve the most recent replan & self-correction reflection records across plans."""
    stmt = select(ReplanRecordModel).order_by(desc(ReplanRecordModel.created_at)).limit(limit)
    if user:
        stmt = stmt.where(ReplanRecordModel.user_id == user.id)
    res = await db.execute(stmt)
    records = list(res.scalars().all())

    return [
        ReplanRecordResponse(
            id=r.id,
            plan_id=r.plan_id,
            step_id=r.step_id,
            task_id=r.task_id,
            user_id=r.user_id,
            iteration=r.iteration,
            error_category=r.error_category,
            error_message=r.error_message,
            diagnosis=r.diagnosis,
            strategy=r.strategy,
            recovery_steps=r.recovery_steps,
            snapshot_id=r.snapshot_id,
            rollback_performed=r.rollback_performed,
            status=r.status,
            created_at=r.created_at.isoformat(),
        )
        for r in records
    ]


@recovery_router.get("/recovery/stats", response_model=RecoveryStatsResponse)
async def get_recovery_statistics(
    user: UserModel | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecoveryStatsResponse:
    """Retrieve aggregate telemetry and success metrics for autonomous self-correction."""
    stmt = select(ReplanRecordModel)
    if user:
        stmt = stmt.where(ReplanRecordModel.user_id == user.id)
    res = await db.execute(stmt)
    records = list(res.scalars().all())

    total = len(records)
    resolved = sum(1 for r in records if r.status in ("resolved", "replanned"))
    rollbacks = sum(1 for r in records if r.rollback_performed)
    escalations = sum(1 for r in records if r.status == "escalated_hitl")

    strategies: dict[str, int] = {}
    categories: dict[str, int] = {}
    for r in records:
        strategies[r.strategy] = strategies.get(r.strategy, 0) + 1
        categories[r.error_category] = categories.get(r.error_category, 0) + 1

    success_rate = round((resolved / total * 100.0), 1) if total > 0 else 100.0

    return RecoveryStatsResponse(
        total_replan_records=total,
        resolved_count=resolved,
        rollback_count=rollbacks,
        hitl_escalation_count=escalations,
        success_rate_percent=success_rate,
        strategy_distribution=strategies,
        error_category_distribution=categories,
    )


@recovery_router.get("/{plan_id}/reflections", response_model=list[ReplanRecordResponse])
async def list_plan_reflections(
    plan_id: str,
    user: UserModel | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReplanRecordResponse]:
    """Retrieve all reflection and replan records for an execution plan."""
    # Verify plan exists
    stmt_plan = select(ExecutionPlanModel).where(ExecutionPlanModel.id == plan_id)
    if user:
        stmt_plan = stmt_plan.where(ExecutionPlanModel.user_id == user.id)
    plan_res = await db.execute(stmt_plan)
    plan = plan_res.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution plan '{plan_id}' not found",
        )

    # Fetch replan records
    stmt = (
        select(ReplanRecordModel)
        .where(ReplanRecordModel.plan_id == plan_id)
        .order_by(desc(ReplanRecordModel.created_at))
    )
    res = await db.execute(stmt)
    records = list(res.scalars().all())

    return [
        ReplanRecordResponse(
            id=r.id,
            plan_id=r.plan_id,
            step_id=r.step_id,
            task_id=r.task_id,
            user_id=r.user_id,
            iteration=r.iteration,
            error_category=r.error_category,
            error_message=r.error_message,
            diagnosis=r.diagnosis,
            strategy=r.strategy,
            recovery_steps=r.recovery_steps,
            snapshot_id=r.snapshot_id,
            rollback_performed=r.rollback_performed,
            status=r.status,
            created_at=r.created_at.isoformat(),
        )
        for r in records
    ]


@recovery_router.post("/{plan_id}/reflections/diagnose", response_model=ReplanRecordResponse)
async def diagnose_and_replan_step(
    plan_id: str,
    req: DiagnoseStepRequest,
    user: UserModel | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReplanRecordResponse:
    """Manually invoke error reflection, state rollback (if applicable), and DAG patching."""
    stmt_plan = select(ExecutionPlanModel).where(ExecutionPlanModel.id == plan_id)
    if user:
        stmt_plan = stmt_plan.where(ExecutionPlanModel.user_id == user.id)
    plan_res = await db.execute(stmt_plan)
    plan = plan_res.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution plan '{plan_id}' not found",
        )

    stmt_step = select(PlanStepModel).where(
        PlanStepModel.id == req.step_id,
        PlanStepModel.plan_id == plan_id,
    )
    step_res = await db.execute(stmt_step)
    step = step_res.scalar_one_or_none()
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan step '{req.step_id}' not found in plan '{plan_id}'",
        )

    error_context = req.error_override or step.error_message or "Manual diagnostic requested"

    coordinator = get_recovery_coordinator()
    _, record, _ = await coordinator.handle_step_failure(
        session=db,
        plan=plan,
        failed_step=step,
        error_context=error_context,
        step_results=None,
    )

    return ReplanRecordResponse(
        id=record.id,
        plan_id=record.plan_id,
        step_id=record.step_id,
        task_id=record.task_id,
        user_id=record.user_id,
        iteration=record.iteration,
        error_category=record.error_category,
        error_message=record.error_message,
        diagnosis=record.diagnosis,
        strategy=record.strategy,
        recovery_steps=record.recovery_steps,
        snapshot_id=record.snapshot_id,
        rollback_performed=record.rollback_performed,
        status=record.status,
        created_at=record.created_at.isoformat(),
    )
