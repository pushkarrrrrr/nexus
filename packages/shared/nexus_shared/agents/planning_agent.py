"""PlanningAgent responsible for goal decomposition and failure recovery replanning."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.agents.base import AgentStepResult, BaseAgent
from packages.shared.nexus_shared.ai.gateway import get_model_gateway
from packages.shared.nexus_shared.models import (
    ExecutionPlanModel,
    PlanStepModel,
    generate_uuid,
    utcnow,
)
from packages.types.nexus_types.schemas import (
    AgentPlan,
    AgentType,
    CompletionRequest,
    PlanStep,
    PlanStepStatus,
)


class PlanningAgent(BaseAgent):
    """Specialized agent that synthesizes execution plans and manages replanning."""

    def __init__(self) -> None:
        super().__init__(
            agent_type=AgentType.PLANNING,
            name="Planning Agent",
            description="Decomposes goals into verifiable dependency DAGs and formulates recovery plans.",
            allowed_tools=["plan_generator", "replan_synthesizer"],
            assigned_model="gpt-4o",
        )
        self.gateway = get_model_gateway()

    async def run(
        self,
        step: PlanStep,
        context: dict[str, Any],
        user_id: str,
        db: AsyncSession,
    ) -> AgentStepResult:
        """Execute a planning step."""
        goal = context.get("goal") or step.description
        steps = await self.generate_steps(goal, context)
        return AgentStepResult(
            success=True,
            result_payload={"plan_steps": [s.model_dump() for s in steps]},
        )

    async def generate_steps(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> list[PlanStep]:
        """Generate an ordered list of PlanSteps with explicit dependencies."""
        prompt = (
            f"Analyze the following goal and decompose it into a clean, verifiable execution plan:\n"
            f"Goal: {goal}\n"
            f"Context: {context or {}}\n\n"
            f"Break this into 2-4 ordered steps. Assign each step to one of: 'research', 'document', 'orchestrator'."
        )

        try:
            req = CompletionRequest(
                prompt=prompt,
                model=self.assigned_model,
                temperature=0.1,
            )
            structured_plan, _ = await self.gateway.complete_structured(req, AgentPlan)
            raw_steps = structured_plan.steps
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "Planning structured LLM completion failed, using heuristic decomposition: %s", exc
            )
            raw_steps = []

        if not raw_steps:
            # Deterministic, robust fallback plan
            lower_goal = goal.lower()
            if "document" in lower_goal or "pdf" in lower_goal or "file" in lower_goal:
                raw_steps = [
                    PlanStep(
                        id=f"step_{generate_uuid('s')[:8]}",
                        index=0,
                        description=f"Inspect documents related to: {goal}",
                        assigned_agent="document",
                        required_tools=["document_indexer"],
                        dependencies=[],
                    ),
                    PlanStep(
                        id=f"step_{generate_uuid('s')[:8]}",
                        index=1,
                        description=f"Synthesize structured findings for: {goal}",
                        assigned_agent="orchestrator",
                        required_tools=["synthesizer"],
                        dependencies=[],
                    ),
                ]
            else:
                raw_steps = [
                    PlanStep(
                        id=f"step_{generate_uuid('s')[:8]}",
                        index=0,
                        description=f"Retrieve grounded knowledge and graph relations for: {goal}",
                        assigned_agent="research",
                        required_tools=["rag_retriever", "graph_explorer"],
                        dependencies=[],
                    ),
                    PlanStep(
                        id=f"step_{generate_uuid('s')[:8]}",
                        index=1,
                        description=f"Synthesize verified conclusions for: {goal}",
                        assigned_agent="orchestrator",
                        required_tools=["synthesizer"],
                        dependencies=[],
                    ),
                ]

        # Ensure index ordering and dependency chaining
        normalized_steps: list[PlanStep] = []
        for i, s in enumerate(raw_steps):
            step_id = s.id or f"step_{i}_{generate_uuid('s')[:6]}"
            # Ensure previous step is a dependency if no explicit dependencies given
            deps = (
                list(s.dependencies)
                if s.dependencies
                else ([normalized_steps[i - 1].id] if i > 0 else [])
            )
            assigned = s.assigned_agent or s.agent or "orchestrator"
            if assigned not in ("orchestrator", "planning", "research", "document"):
                assigned = "orchestrator"

            normalized = PlanStep(
                id=step_id,
                index=i,
                description=s.description or s.name or f"Execute step {i}",
                name=s.name or s.description or f"Step {i}",
                assigned_agent=assigned,
                agent=assigned,
                required_tools=s.required_tools or ([s.tool] if s.tool else []),
                dependencies=deps,
                status=PlanStepStatus.PENDING.value,
            )
            normalized_steps.append(normalized)

        return normalized_steps

    async def replan(
        self,
        failed_step: PlanStepModel,
        error_context: str,
        plan_id: str,
        db: AsyncSession,
    ) -> list[PlanStepModel]:
        """Formulate and persist recovery steps in response to a failed step."""
        query = await db.execute(select(ExecutionPlanModel).where(ExecutionPlanModel.id == plan_id))
        plan = query.scalar_one_or_none()
        if not plan:
            raise ValueError(f"Plan '{plan_id}' not found")

        self.logger.info(
            "replanning_initiated",
            plan_id=plan_id,
            failed_step_id=failed_step.id,
            error=error_context,
            current_replan_count=plan.replan_count,
        )

        plan.replan_count += 1
        plan.status = "re-planning"
        plan.updated_at = utcnow()

        # Find existing max step index
        steps_query = await db.execute(
            select(PlanStepModel)
            .where(PlanStepModel.plan_id == plan_id)
            .order_by(PlanStepModel.index.desc())
        )
        existing_steps = list(steps_query.scalars().all())
        next_index = (existing_steps[0].index + 1) if existing_steps else 1

        # Synthesize recovery step
        recovery_desc = f"Recovery: Retry with alternative query or fallback retrieval following failure: {error_context[:80]}"
        recovery_step = PlanStepModel(
            id=generate_uuid("pstep"),
            plan_id=plan.id,
            index=next_index,
            description=recovery_desc,
            assigned_agent="research"
            if failed_step.assigned_agent == "research"
            else "orchestrator",
            required_tools=["fallback_resolver"],
            dependencies=list(failed_step.dependencies or []),
            status="pending",
        )
        db.add(recovery_step)
        await db.commit()
        await db.refresh(recovery_step)

        self.logger.info(
            "replanning_completed",
            plan_id=plan_id,
            new_step_id=recovery_step.id,
            replan_count=plan.replan_count,
        )
        return [recovery_step]
