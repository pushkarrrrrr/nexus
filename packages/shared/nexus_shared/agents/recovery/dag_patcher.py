"""Topological DAG Patcher and Step Splicer for Execution Plans."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.agents.recovery.schemas import SelfCorrectionProposal
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    ExecutionPlanModel,
    PlanStepModel,
    generate_uuid,
    utcnow,
)

logger = get_logger("nexus.recovery.dag_patcher")


class DAGPatcher:
    """Performs in-place DAG surgery to splice recovery steps and rewire dependencies."""

    @classmethod
    async def patch_plan(
        cls,
        session: AsyncSession,
        plan: ExecutionPlanModel,
        failed_step: PlanStepModel,
        proposal: SelfCorrectionProposal,
    ) -> list[PlanStepModel]:
        """Splice recovery steps into the plan and re-route downstream dependencies."""
        # 1. Fetch all steps ordered by index
        query = await session.execute(
            select(PlanStepModel)
            .where(PlanStepModel.plan_id == plan.id)
            .order_by(PlanStepModel.index.asc())
        )
        existing_steps = list(query.scalars().all())

        # 2. Mark failed step as superseded
        failed_step.status = "superseded"
        failed_step.completed_at = utcnow()

        num_recovery_steps = len(proposal.recovery_steps)
        if num_recovery_steps == 0:
            logger.warning("no_recovery_steps_in_proposal", plan_id=plan.id)
            return []

        # 3. Shift subsequent steps down to make room
        insert_start_index = failed_step.index + 1
        for step in existing_steps:
            if step.id != failed_step.id and step.index >= insert_start_index:
                step.index += num_recovery_steps

        # 4. Instantiate and insert recovery steps
        created_steps: list[PlanStepModel] = []

        for idx, rec in enumerate(proposal.recovery_steps):
            step_id = generate_uuid("pstep")
            # Dependency chaining: first recovery step inherits failed step's deps;
            # subsequent recovery steps chain to previous recovery step
            if idx == 0:
                deps = list(failed_step.dependencies or [])
            else:
                deps = [created_steps[idx - 1].id]

            recovery_step = PlanStepModel(
                id=step_id,
                plan_id=plan.id,
                index=insert_start_index + idx,
                description=rec.description,
                assigned_agent=rec.assigned_agent,
                required_tools=list(rec.required_tools),
                dependencies=deps,
                status="pending",
                is_recovery_step=True,
                replaces_step_id=failed_step.id,
            )
            session.add(recovery_step)
            created_steps.append(recovery_step)

        # 5. Rewire downstream steps: any pending step depending on failed_step now depends on last recovery step
        last_recovery_id = created_steps[-1].id
        for step in existing_steps:
            if step.id != failed_step.id and step.dependencies:
                new_deps: list[str] = []
                for dep in step.dependencies:
                    if dep == failed_step.id:
                        new_deps.append(last_recovery_id)
                    else:
                        new_deps.append(dep)
                step.dependencies = new_deps

        # 6. Update plan status
        plan.replan_count += 1
        plan.status = "re-planning"
        plan.updated_at = utcnow()

        await session.flush()

        logger.info(
            "dag_patched_successfully",
            plan_id=plan.id,
            failed_step_id=failed_step.id,
            added_steps=len(created_steps),
            replan_count=plan.replan_count,
        )
        return created_steps
