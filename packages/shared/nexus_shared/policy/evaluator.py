"""NEXUS Policy Engine

Core evaluation pipeline for actions, capability verification,
canonical path normalization, atomic ONE_TIME permission consumption,
and immutable append-only audit ledger logging.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    ApprovalRequestModel,
    AuditLogModel,
    UserPermissionModel,
)
from packages.shared.nexus_shared.policy.registry import (
    CapabilityRegistry,
    get_capability_registry,
)
from packages.shared.nexus_shared.policy.utils import (
    match_resource_pattern,
    normalize_resource_target,
)
from packages.shared.nexus_shared.reversal.manager import SnapshotManager

logger = get_logger("nexus.policy.evaluator")

PolicyVerdict = Literal["ALLOWED", "REQUIRES_APPROVAL", "BLOCKED"]


class PolicyDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: PolicyVerdict
    capability_name: str
    risk_level: str
    reason: str
    approval_id: str | None = None
    matching_permission_id: str | None = None
    affected_resource: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PolicyEngine:
    """Evaluates agent capability invocations against registry rules and user permissions."""

    def __init__(self, registry: CapabilityRegistry | None = None) -> None:
        self.registry = registry or get_capability_registry()
        self._snapshot_manager = SnapshotManager()

    async def evaluate_action(
        self,
        db: AsyncSession,
        user_id: str,
        capability_name: str,
        resource_target: str,
        params: dict[str, Any] | None = None,
        session_id: str | None = None,
        ip_address: str | None = None,
        task_id: str | None = None,
        step_id: str | None = None,
        agent_name: str = "orchestrator",
        tool_name: str | None = None,
    ) -> PolicyDecision:
        now = datetime.now(UTC)
        params = params or {}
        effective_tool = tool_name or capability_name
        normalized_resource = normalize_resource_target(resource_target)

        # 1. Capability Registry lookup
        cap = self.registry.get(capability_name)
        if cap is None or not cap.is_active:
            reason = (
                f"Capability '{capability_name}' is inactive."
                if cap and not cap.is_active
                else f"Unknown capability '{capability_name}'."
            )
            decision = PolicyDecision(
                verdict="BLOCKED",
                capability_name=capability_name,
                risk_level="CRITICAL",
                reason=reason,
                affected_resource=normalized_resource,
            )
            await self._log_audit(
                db=db,
                user_id=user_id,
                session_id=session_id,
                step_id=step_id,
                agent_name=agent_name,
                tool_name=effective_tool,
                action_type=cap.category if cap else "EXTERNAL_ACTION",
                risk_level="CRITICAL",
                event_type="ACTION_BLOCKED",
                capability_name=capability_name,
                status="BLOCKED",
                policy_verdict="BLOCKED",
                details={
                    "reason": reason,
                    "target": normalized_resource,
                    "raw_target": resource_target,
                    "params": params,
                },
                ip_address=ip_address,
            )
            await db.commit()
            return decision

        risk_level = cap.default_risk_level
        action_category = cap.category

        # 2. Strict CRITICAL risk check
        # CRITICAL actions can NEVER use standing permissions and require explicit pending approval
        is_critical = risk_level == "CRITICAL"

        # 3. Permission verification (if not CRITICAL)
        if not is_critical:
            stmt = (
                select(UserPermissionModel)
                .where(
                    UserPermissionModel.user_id == user_id,
                    UserPermissionModel.capability_name == capability_name,
                    or_(
                        UserPermissionModel.expires_at.is_(None),
                        UserPermissionModel.expires_at > now,
                    ),
                )
                .order_by(UserPermissionModel.created_at.desc())
            )

            result = await db.execute(stmt)
            permissions = result.scalars().all()

            for perm in permissions:
                if match_resource_pattern(normalized_resource, perm.resource_pattern):
                    # Atomic TOCTOU Protection for ONE_TIME Permissions
                    if perm.scope == "ONE_TIME":
                        del_stmt = delete(UserPermissionModel).where(
                            UserPermissionModel.id == perm.id,
                            UserPermissionModel.user_id == user_id,
                        )
                        del_res = await db.execute(del_stmt)
                        await db.flush()
                        row_count = getattr(del_res, "rowcount", -1)
                        if row_count == 0:
                            # Already consumed concurrently, test next matching permission
                            continue

                    decision = PolicyDecision(
                        verdict="ALLOWED",
                        capability_name=capability_name,
                        risk_level=risk_level,
                        reason=f"Authorized under {perm.scope} permission grant.",
                        matching_permission_id=perm.id,
                        affected_resource=normalized_resource,
                    )
                    await self._log_audit(
                        db=db,
                        user_id=user_id,
                        session_id=session_id,
                        step_id=step_id,
                        agent_name=agent_name,
                        tool_name=effective_tool,
                        action_type=action_category,
                        risk_level=risk_level,
                        event_type="ACTION_ALLOWED",
                        capability_name=capability_name,
                        status="SUCCESS",
                        policy_verdict="ALLOWED",
                        details={
                            "reason": decision.reason,
                            "permission_id": perm.id,
                            "permission_scope": perm.scope,
                            "pattern": perm.resource_pattern,
                            "target": normalized_resource,
                            "params": params,
                        },
                        ip_address=ip_address,
                    )
                    await db.commit()
                    return decision

        # 4. If no valid permission, generate a PENDING ApprovalRequest
        approval_expires = now + timedelta(minutes=5)
        reason_text = (
            f"Mandatory approval required for CRITICAL system capability '{capability_name}' on '{normalized_resource}'."
            if is_critical
            else f"Capability '{capability_name}' on target '{normalized_resource}' requires user authorization."
        )

        # Classify reversibility and capture pre-state diff if reversible file operation
        action_type, is_reversible = SnapshotManager.classify_action(capability_name)
        snapshot_id: str | None = None
        diff_preview: str | None = None

        if is_reversible and normalized_resource:
            try:
                proposed_content = params.get("content")
                snapshot = await self._snapshot_manager.create_snapshot(
                    db=db,
                    user_id=user_id,
                    capability_name=capability_name,
                    action_type=action_type,
                    target_path=normalized_resource,
                    proposed_content=proposed_content,
                    task_id=task_id,
                    step_id=step_id,
                    auto_apply=False,
                )
                snapshot_id = snapshot.id
                diff_preview = snapshot.diff_patch
            except (OSError, RuntimeError) as e:
                logger.warning("snapshot_pre_capture_failed", error=str(e))

        approval = ApprovalRequestModel(
            user_id=user_id,
            task_id=task_id,
            step_id=step_id,
            capability_name=capability_name,
            action_category=action_category,
            risk_level=risk_level,
            reason=reason_text,
            affected_resources=[normalized_resource] if normalized_resource else [],
            parameters=params,
            status="PENDING",
            expires_at=approval_expires,
            snapshot_id=snapshot_id,
            diff_preview=diff_preview,
            is_reversible=is_reversible,
        )
        db.add(approval)
        await db.flush()

        decision = PolicyDecision(
            verdict="REQUIRES_APPROVAL",
            capability_name=capability_name,
            risk_level=risk_level,
            reason=reason_text,
            approval_id=approval.id,
            affected_resource=normalized_resource,
        )

        await self._log_audit(
            db=db,
            user_id=user_id,
            session_id=session_id,
            step_id=step_id,
            agent_name=agent_name,
            tool_name=effective_tool,
            action_type=action_category,
            risk_level=risk_level,
            event_type="APPROVAL_REQUESTED",
            capability_name=capability_name,
            status="SUCCESS",
            policy_verdict="REQUIRES_APPROVAL",
            approval_id=approval.id,
            details={
                "approval_id": approval.id,
                "reason": reason_text,
                "target": normalized_resource,
                "params": params,
                "expires_at": approval_expires.isoformat(),
            },
            ip_address=ip_address,
        )
        await db.commit()
        return decision

    async def _log_audit(
        self,
        db: AsyncSession,
        user_id: str,
        session_id: str | None,
        step_id: str | None,
        agent_name: str,
        tool_name: str,
        action_type: str,
        risk_level: str,
        event_type: str,
        capability_name: str | None,
        status: str,
        policy_verdict: str,
        details: dict[str, Any],
        approval_id: str | None = None,
        ip_address: str | None = None,
    ) -> AuditLogModel:
        """Create append-only audit log entry."""
        audit_entry = AuditLogModel(
            user_id=user_id,
            session_id=session_id or "policy_session",
            step_id=step_id,
            agent_name=agent_name,
            tool_name=tool_name,
            action_type=action_type,
            risk_level=risk_level,
            inputs=details.get("params", {}),
            outputs={"verdict": policy_verdict, "status": status},
            policy_verdict=policy_verdict,
            event_type=event_type,
            capability_name=capability_name,
            details=details,
            ip_address=ip_address,
            status=status,
            approval_id=approval_id,
            duration_ms=1.0,
            created_at=datetime.now(UTC),
            timestamp=datetime.now(UTC),
        )
        db.add(audit_entry)
        await db.flush()
        return audit_entry
