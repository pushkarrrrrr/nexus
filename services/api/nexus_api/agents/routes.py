"""REST API routes for Phase 8 NEXUS Multi-Agent Orchestrator & Planning."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.agents import get_orchestrator_agent
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    ExecutionPlanModel,
    PlanStepModel,
    UserModel,
)
from packages.types.nexus_types.schemas import (
    AgentExecuteRequest,
    AgentExecuteResponse,
    AgentRosterItem,
    ExecutionPlan,
    PlanStep,
    ReplanRequest,
)
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.database import get_db
from services.api.nexus_api.websocket import broadcast_event

logger = get_logger("nexus.api.agents")
agents_router = APIRouter(prefix="/agents", tags=["agents"])


def _format_execution_plan(plan: ExecutionPlanModel, steps: list[PlanStepModel]) -> ExecutionPlan:
    """Format ORM ExecutionPlanModel and its PlanStepModels to the Pydantic ExecutionPlan schema."""
    formatted_steps = [
        PlanStep(
            id=s.id,
            index=s.index,
            description=s.description,
            name=s.description,
            assigned_agent=s.assigned_agent,
            required_tools=list(s.required_tools or []),
            dependencies=list(s.dependencies or []),
            status=s.status,
            retry_count=s.retry_count,
            max_retries=s.max_retries,
            result=s.result_payload,
            error=s.error_message,
            started_at=s.started_at,
            completed_at=s.completed_at,
        )
        for s in steps
    ]

    return ExecutionPlan(
        id=plan.id,
        task_id=plan.task_id,
        user_id=plan.user_id,
        goal=plan.goal,
        steps=formatted_steps,
        current_step_index=plan.current_step_index,
        status=plan.status,
        replan_count=plan.replan_count,
        max_replans=plan.max_replans,
        plan_metadata=dict(plan.plan_metadata or {}),
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@agents_router.get("/roster", response_model=list[AgentRosterItem])
async def get_agent_roster(
    current_user: UserModel = Depends(get_current_user),
) -> list[AgentRosterItem]:
    """Retrieve the registered multi-agent roster with roles, models, and capabilities."""
    orchestrator = get_orchestrator_agent()
    return orchestrator.get_roster()


@agents_router.post("/execute", response_model=AgentExecuteResponse)
async def execute_agent_goal(
    req: AgentExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> AgentExecuteResponse:
    """
    Autonomous goal execution entrypoint: decomposes goal, creates Task & ExecutionPlan,
    resolves step dependencies, and executes across specialized agents.
    """
    orchestrator = get_orchestrator_agent()

    async def event_publisher(event_type: str, item: Any) -> None:
        payload: dict[str, Any] = {}
        if hasattr(item, "id"):
            payload["id"] = item.id
        if hasattr(item, "status"):
            payload["status"] = item.status
        if hasattr(item, "description"):
            payload["description"] = item.description
        await broadcast_event(
            event_type=f"agent.{event_type}",
            session_id=req.session_id or "default",
            payload=payload,
        )

    response = await orchestrator.execute_goal(
        goal=req.goal,
        user_id=str(current_user.id),
        session_id=req.session_id,
        context=req.context,
        db=db,
        event_callback=event_publisher,
    )

    return response


@agents_router.get("/plans/{task_id}", response_model=ExecutionPlan)
async def get_execution_plan_for_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> ExecutionPlan:
    """Retrieve the structured ExecutionPlan and step history for a task with user isolation."""
    query = await db.execute(
        select(ExecutionPlanModel)
        .where(
            ExecutionPlanModel.task_id == task_id,
            ExecutionPlanModel.user_id == current_user.id,
        )
        .order_by(ExecutionPlanModel.created_at.desc())
        .limit(1)
    )
    plan = query.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution plan not found for task '{task_id}'",
        )

    steps_query = await db.execute(
        select(PlanStepModel)
        .where(PlanStepModel.plan_id == plan.id)
        .order_by(PlanStepModel.index.asc())
    )
    steps = list(steps_query.scalars().all())

    return _format_execution_plan(plan, steps)


@agents_router.post("/plans/{plan_id}/replan", response_model=ExecutionPlan)
async def trigger_replan(
    plan_id: str,
    req: ReplanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> ExecutionPlan:
    """Force or resume a recovery replan for an execution plan."""
    query = await db.execute(
        select(ExecutionPlanModel).where(
            ExecutionPlanModel.id == plan_id,
            ExecutionPlanModel.user_id == current_user.id,
        )
    )
    plan = query.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution plan '{plan_id}' not found",
        )

    if plan.replan_count >= plan.max_replans:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan has reached maximum replan count ({plan.max_replans})",
        )

    # Find the last step (or failed step)
    steps_query = await db.execute(
        select(PlanStepModel)
        .where(PlanStepModel.plan_id == plan.id)
        .order_by(PlanStepModel.index.desc())
    )
    all_steps = list(steps_query.scalars().all())
    target_step = next(
        (s for s in all_steps if s.status == "failed"), all_steps[0] if all_steps else None
    )

    if not target_step:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No steps available to replan against",
        )

    orchestrator = get_orchestrator_agent()
    await orchestrator.planning_agent.replan(
        failed_step=target_step,
        error_context=req.error_context or req.reason or "Manual replan requested",
        plan_id=plan.id,
        db=db,
    )

    # Reload refreshed steps
    refreshed_steps_query = await db.execute(
        select(PlanStepModel)
        .where(PlanStepModel.plan_id == plan.id)
        .order_by(PlanStepModel.index.asc())
    )
    refreshed_steps = list(refreshed_steps_query.scalars().all())

    return _format_execution_plan(plan, refreshed_steps)
