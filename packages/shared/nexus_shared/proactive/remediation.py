"""Remediation and Self-Healing Coordinator enforcing Policy Engine HITL safety invariants."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    ApprovalRequestModel,
    ProactiveTriggerModel,
    TriggerEventModel,
)
from packages.shared.nexus_shared.policy.registry import get_capability_registry
from packages.shared.nexus_shared.proactive.models import TriggerEvaluationResult

logger = get_logger("nexus.proactive.remediation")


class RemediationCoordinator:
    """Coordinates self-healing actions, strictly gating mutating interventions behind Human-in-the-Loop approvals."""

    def __init__(
        self,
        event_broadcaster: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self._broadcaster = event_broadcaster

    async def handle_evaluation_result(
        self,
        session: AsyncSession,
        trigger: ProactiveTriggerModel,
        reason: str,
        observed_data: dict[str, Any],
    ) -> TriggerEvaluationResult:
        """Handle a triggered proactive condition.

        Strict Safety Rule:
        If action_capability is RiskLevel.HIGH or mutating (e.g. remediation.execute_fix),
        we pause execution, create an ApprovalRequestModel, log TriggerEventModel as
        'awaiting_approval', and notify client surfaces via WebSocket.
        """
        cap_registry = get_capability_registry()
        cap_name = trigger.action_capability
        cap_def = cap_registry.get(cap_name)
        risk_level = cap_def.default_risk_level if cap_def else "HIGH"
        category = cap_def.category if cap_def else "SYSTEM_CONTROL"

        requires_hitl = risk_level in ("HIGH", "CRITICAL")

        now = datetime.now(UTC)
        trigger.last_triggered_at = now
        trigger.trigger_count += 1
        trigger.updated_at = now

        approval_record: ApprovalRequestModel | None = None

        if requires_hitl:
            # 1. Mutating Intervention: Create Approval Request and halt
            affected_res = [str(trigger.action_params.get("target", "system"))]
            approval_record = ApprovalRequestModel(
                user_id=trigger.user_id,
                capability_name=cap_name,
                action_category=category,
                risk_level=risk_level,
                reason=f"Proactive trigger '{trigger.name}' detected: {reason}",
                affected_resources=affected_res,
                parameters=trigger.action_params,
                status="PENDING",
                diff_preview=trigger.action_params.get(
                    "diff_preview", f"Remediation: {cap_name}\nTarget: {affected_res[0]}"
                ),
                is_reversible=trigger.action_params.get("is_reversible", False),
            )
            session.add(approval_record)
            await session.flush()

            event_record = TriggerEventModel(
                trigger_id=trigger.id,
                user_id=trigger.user_id,
                event_type=f"proactive.{trigger.trigger_type}",
                observed_data=observed_data,
                action_proposed=cap_name,
                approval_id=approval_record.id,
                status="awaiting_approval",
                result_payload={"reason": reason, "risk_level": risk_level},
            )
            session.add(event_record)
            await session.commit()
            await session.refresh(trigger)
            await session.refresh(event_record)

            logger.info(
                "proactive_intervention_gated",
                trigger_id=trigger.id,
                trigger_name=trigger.name,
                approval_id=approval_record.id,
                risk_level=risk_level,
            )

            # Broadcast WebSocket notification
            if self._broadcaster:
                await self._broadcaster(
                    "approval_required",
                    {
                        "approval_id": approval_record.id,
                        "id": approval_record.id,
                        "trigger_id": trigger.id,
                        "trigger_name": trigger.name,
                        "capability_name": cap_name,
                        "risk_level": risk_level,
                        "reason": approval_record.reason,
                        "affected_resources": affected_res,
                        "parameters": trigger.action_params,
                        "source": "proactive_trigger",
                        "created_at": approval_record.created_at.isoformat(),
                    },
                )
                await self._broadcaster(
                    "trigger_detected",
                    {
                        "event_id": event_record.id,
                        "trigger_id": trigger.id,
                        "trigger_name": trigger.name,
                        "status": "awaiting_approval",
                        "observed_data": observed_data,
                        "reason": reason,
                    },
                )

            return TriggerEvaluationResult(
                triggered=True,
                trigger_id=trigger.id,
                trigger_name=trigger.name,
                reason=reason,
                observed_data=observed_data,
                action_capability=cap_name,
                action_params=trigger.action_params,
                requires_approval=True,
                approval_id=approval_record.id,
                status="awaiting_approval",
            )
        else:
            # 2. Autonomous LOW-risk read / observation
            from packages.shared.nexus_shared.tools.registry import get_tool_registry

            tool_reg = get_tool_registry()
            tool = tool_reg.get(cap_name)
            tool_result_payload: dict[str, Any] = {"status": "executed", "reason": reason}

            if tool:
                try:
                    tool_res = await tool.execute(
                        user_id=trigger.user_id, params=trigger.action_params
                    )
                    out = tool_res.output
                    if hasattr(out, "model_dump"):
                        out_data = out.model_dump(mode="json")
                    elif isinstance(out, dict):
                        out_data = out
                    else:
                        out_data = str(out) if out is not None else None
                    tool_result_payload = {"output": out_data, "success": tool_res.success}
                except Exception as e:  # noqa: BLE001
                    logger.error("autonomous_tool_execution_failed", tool=cap_name, error=str(e))
                    tool_result_payload = {"error": str(e)}

            event_record = TriggerEventModel(
                trigger_id=trigger.id,
                user_id=trigger.user_id,
                event_type=f"proactive.{trigger.trigger_type}",
                observed_data=observed_data,
                action_proposed=cap_name,
                status="executed",
                result_payload=tool_result_payload,
            )
            session.add(event_record)
            await session.commit()
            await session.refresh(trigger)
            await session.refresh(event_record)

            if self._broadcaster:
                await self._broadcaster(
                    "trigger_detected",
                    {
                        "event_id": event_record.id,
                        "trigger_id": trigger.id,
                        "trigger_name": trigger.name,
                        "status": "executed",
                        "observed_data": observed_data,
                        "reason": reason,
                    },
                )

            return TriggerEvaluationResult(
                triggered=True,
                trigger_id=trigger.id,
                trigger_name=trigger.name,
                reason=reason,
                observed_data=observed_data,
                action_capability=cap_name,
                action_params=trigger.action_params,
                requires_approval=False,
                status="executed",
            )
