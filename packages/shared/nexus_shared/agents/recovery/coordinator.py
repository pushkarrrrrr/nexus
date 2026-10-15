"""Self-Correction Coordinator integrating classification, reflection, rollback, and DAG surgery."""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.agents.recovery.classifier import ErrorClassifier
from packages.shared.nexus_shared.agents.recovery.dag_patcher import DAGPatcher
from packages.shared.nexus_shared.agents.recovery.reflector import SelfCorrectionReflector
from packages.shared.nexus_shared.agents.recovery.schemas import SelfCorrectionProposal
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    ApprovalRequestModel,
    ExecutionPlanModel,
    PlanStepModel,
    ReplanRecordModel,
    generate_uuid,
    utcnow,
)
from packages.shared.nexus_shared.reversal import SnapshotManager

logger = get_logger("nexus.recovery.coordinator")


class SelfCorrectionCoordinator:
    """Orchestrates end-to-end autonomous error reflection, state reversal, and dynamic DAG patching."""

    def __init__(
        self,
        reflector: SelfCorrectionReflector | None = None,
        event_broadcaster: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self.reflector = reflector or SelfCorrectionReflector()
        self._broadcaster = event_broadcaster

    def set_broadcaster(
        self, broadcaster: Callable[[str, dict[str, Any]], Awaitable[None]]
    ) -> None:
        self._broadcaster = broadcaster

    async def handle_step_failure(
        self,
        session: AsyncSession,
        plan: ExecutionPlanModel,
        failed_step: PlanStepModel,
        error_context: str,
        step_results: dict[str, Any] | None = None,
    ) -> tuple[list[PlanStepModel], ReplanRecordModel, SelfCorrectionProposal]:
        """Diagnose failure, execute state rollback if needed, patch DAG, and record replan record."""
        # 1. Classify error
        error_category = ErrorClassifier.classify(
            error_message=error_context,
            tool_result=failed_step.result_payload if isinstance(failed_step.result_payload, dict) else None,
        )

        # 2. Check for pre-execution snapshot in step result
        snapshot_id: str | None = None
        if isinstance(failed_step.result_payload, dict):
            snapshot_id = failed_step.result_payload.get("snapshot_id")

        has_snapshot = bool(snapshot_id)

        # 3. Broadcast reflection started
        if self._broadcaster:
            await self._broadcaster(
                "reflection_started",
                {
                    "plan_id": plan.id,
                    "step_id": failed_step.id,
                    "category": error_category,
                    "error": error_context[:200],
                },
            )

        # 4. Synthesize reflection & remediation proposal
        proposal = await self.reflector.reflect(
            goal=plan.goal,
            failed_step=failed_step,
            error_context=error_context,
            error_category=error_category,
            prior_results=step_results,
            has_snapshot=has_snapshot,
        )

        # 5. Revert file mutations if required and available
        rollback_performed = False
        if proposal.requires_rollback and snapshot_id:
            try:
                await SnapshotManager.revert_action(
                    db=session,
                    snapshot_id=snapshot_id,
                    user_id=plan.user_id,
                )
                rollback_performed = True
                logger.info(
                    "filesystem_rollback_executed_prior_to_replan",
                    snapshot_id=snapshot_id,
                    step_id=failed_step.id,
                )
                if self._broadcaster:
                    await self._broadcaster(
                        "state_reverted",
                        {
                            "plan_id": plan.id,
                            "step_id": failed_step.id,
                            "snapshot_id": snapshot_id,
                        },
                    )
            except Exception as e:  # noqa: BLE001
                logger.error("rollback_execution_failed", error=str(e), snapshot_id=snapshot_id)

        # 6. Check replan budget cap
        exceeded_budget = plan.replan_count >= plan.max_replans
        replan_status = "replanned"

        if exceeded_budget or proposal.requires_hitl:
            # Escalate to Human-in-the-Loop
            replan_status = "escalated_hitl"
            strategy_val = (
                proposal.strategy.value
                if hasattr(proposal.strategy, "value")
                else str(proposal.strategy)
            )
            approval = ApprovalRequestModel(
                user_id=plan.user_id,
                task_id=plan.task_id,
                step_id=failed_step.id,
                capability_name="orchestrator.replan_recovery",
                action_category="SYSTEM_CONTROL",
                risk_level="HIGH",
                reason=f"Self-correction requires approval: {proposal.diagnosis}",
                affected_resources=[f"plan:{plan.id}:step:{failed_step.id}"],
                parameters={
                    "plan_id": plan.id,
                    "step_id": failed_step.id,
                    "diagnosis": proposal.diagnosis,
                    "strategy": strategy_val,
                    "error": error_context[:200],
                },
                status="PENDING",
            )
            session.add(approval)
            await session.flush()

            if self._broadcaster:
                await self._broadcaster(
                    "approval_required",
                    {
                        "approval_id": approval.id,
                        "plan_id": plan.id,
                        "step_id": failed_step.id,
                        "reason": approval.reason,
                        "risk_level": "HIGH",
                    },
                )
                await self._broadcaster(
                    "replan_escalated",
                    {
                        "plan_id": plan.id,
                        "step_id": failed_step.id,
                        "approval_id": approval.id,
                        "diagnosis": proposal.diagnosis,
                    },
                )

        # 7. Splicing recovery steps into DAG
        created_steps = await DAGPatcher.patch_plan(
            session=session,
            plan=plan,
            failed_step=failed_step,
            proposal=proposal,
        )

        # 8. Persist ReplanRecordModel
        record = ReplanRecordModel(
            id=generate_uuid("replan"),
            plan_id=plan.id,
            step_id=failed_step.id,
            task_id=plan.task_id,
            user_id=plan.user_id,
            iteration=plan.replan_count,
            error_category=proposal.error_category,
            error_message=error_context[:1000],
            diagnosis=proposal.diagnosis,
            strategy=proposal.strategy,
            recovery_steps=[s.model_dump() for s in proposal.recovery_steps],
            snapshot_id=snapshot_id,
            rollback_performed=rollback_performed,
            status=replan_status,
            created_at=utcnow(),
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)

        # 9. Broadcast replan synthesized
        if self._broadcaster:
            await self._broadcaster(
                "replan_synthesized",
                {
                    "plan_id": plan.id,
                    "replan_id": record.id,
                    "strategy": proposal.strategy,
                    "diagnosis": proposal.diagnosis,
                    "recovery_step_count": len(created_steps),
                },
            )

        return created_steps, record, proposal
