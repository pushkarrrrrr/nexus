"""NEXUS Approval & Permission Lifecycle Manager

Handles resolution of Human-in-the-Loop approvals, inline expiration enforcement,
standing permission constraints, and permission revocation.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    ApprovalRequestModel,
    AuditLogModel,
    UserPermissionModel,
)

logger = get_logger("nexus.policy.manager")


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime has UTC timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class PolicyManager:
    """Manages approvals, permission grants, and security authorizations."""

    async def resolve_approval(
        self,
        db: AsyncSession,
        user_id: str,
        approval_id: str,
        decision: str,
        chosen_scope: str | None = None,
        session_ttl_minutes: int = 60,
        ip_address: str | None = None,
    ) -> ApprovalRequestModel:
        """Resolve a pending approval request with strict inline expiration checks."""
        now = datetime.now(UTC)
        decision_upper = decision.strip().upper()

        if decision_upper not in ("APPROVED", "DENIED"):
            raise ValueError(f"Invalid decision '{decision}'. Must be 'APPROVED' or 'DENIED'.")

        stmt = select(ApprovalRequestModel).where(
            ApprovalRequestModel.id == approval_id,
            ApprovalRequestModel.user_id == user_id,
        )
        res = await db.execute(stmt)
        approval = res.scalar_one_or_none()

        if approval is None:
            raise ValueError(f"Approval request '{approval_id}' not found for user.")

        if approval.status != "PENDING":
            raise ValueError(f"Approval request '{approval_id}' is already {approval.status}.")

        # Mandatory Safeguard: Inline Expiration Enforcement
        exp = ensure_utc(approval.expires_at)
        if exp and exp < now:
            approval.status = "EXPIRED"
            approval.resolved_at = now
            audit_entry = AuditLogModel(
                user_id=user_id,
                session_id="policy_session",
                agent_name="system",
                tool_name=approval.capability_name,
                action_type=approval.action_category,
                risk_level=approval.risk_level,
                inputs={"approval_id": approval.id, "attempted_decision": decision_upper},
                outputs={"status": "EXPIRED", "error": "Approval request has expired"},
                policy_verdict="EXPIRED",
                event_type="APPROVAL_RESOLVED",
                capability_name=approval.capability_name,
                status="DENIED",
                approval_id=approval.id,
                details={"reason": "Approval expired inline prior to resolution"},
                ip_address=ip_address,
                duration_ms=1.0,
                created_at=now,
                timestamp=now,
            )
            db.add(audit_entry)
            await db.commit()
            raise ValueError("Approval request has expired and cannot be resolved.")

        # Handle DENIED
        if decision_upper == "DENIED":
            approval.status = "DENIED"
            approval.resolved_at = now

            audit_entry = AuditLogModel(
                user_id=user_id,
                session_id="policy_session",
                agent_name="user",
                tool_name=approval.capability_name,
                action_type=approval.action_category,
                risk_level=approval.risk_level,
                inputs={"approval_id": approval.id, "decision": "DENIED"},
                outputs={"status": "DENIED"},
                policy_verdict="DENIED",
                event_type="APPROVAL_RESOLVED",
                capability_name=approval.capability_name,
                status="DENIED",
                approval_id=approval.id,
                details={"decision": "DENIED", "approval_id": approval.id},
                ip_address=ip_address,
                duration_ms=1.0,
                created_at=now,
                timestamp=now,
            )
            db.add(audit_entry)
            await db.commit()
            await db.refresh(approval)
            return approval

        # Handle APPROVED
        scope = (chosen_scope or "ONE_TIME").upper()
        if scope not in ("ONE_TIME", "SESSION", "STANDING"):
            raise ValueError(f"Invalid scope '{scope}'. Must be ONE_TIME, SESSION, or STANDING.")

        # Standing permission constraint: LOW risk READ only
        if scope == "STANDING" and (
            approval.risk_level != "LOW" or approval.action_category != "READ"
        ):
            raise ValueError(
                "Standing permissions are strictly restricted to LOW-risk READ capabilities."
            )

        approval.status = "APPROVED"
        approval.approved_scope = scope
        approval.resolved_at = now

        # Compute expiration for the granted permission
        if scope == "STANDING":
            perm_expires = None
        elif scope == "SESSION":
            perm_expires = now + timedelta(minutes=session_ttl_minutes)
        else:  # ONE_TIME
            perm_expires = now + timedelta(minutes=15)

        pattern = "*"
        if approval.affected_resources and len(approval.affected_resources) > 0:
            pattern = approval.affected_resources[0]

        perm = UserPermissionModel(
            user_id=user_id,
            capability_name=approval.capability_name,
            scope=scope,
            resource_pattern=pattern,
            expires_at=perm_expires,
        )
        db.add(perm)
        await db.flush()

        audit_entry = AuditLogModel(
            user_id=user_id,
            session_id="policy_session",
            agent_name="user",
            tool_name=approval.capability_name,
            action_type=approval.action_category,
            risk_level=approval.risk_level,
            inputs={
                "approval_id": approval.id,
                "decision": "APPROVED",
                "scope": scope,
            },
            outputs={"status": "APPROVED", "permission_id": perm.id},
            policy_verdict="APPROVED",
            event_type="APPROVAL_RESOLVED",
            capability_name=approval.capability_name,
            status="SUCCESS",
            approval_id=approval.id,
            details={
                "approval_id": approval.id,
                "decision": "APPROVED",
                "scope": scope,
                "permission_id": perm.id,
                "resource_pattern": pattern,
                "expires_at": perm_expires.isoformat() if perm_expires else None,
            },
            ip_address=ip_address,
            duration_ms=1.0,
            created_at=now,
            timestamp=now,
        )
        db.add(audit_entry)
        await db.commit()
        await db.refresh(approval)
        return approval

    async def revoke_permission(
        self,
        db: AsyncSession,
        user_id: str,
        permission_id: str,
        ip_address: str | None = None,
    ) -> bool:
        """Revoke an active permission grant."""
        stmt = select(UserPermissionModel).where(
            UserPermissionModel.id == permission_id,
            UserPermissionModel.user_id == user_id,
        )
        res = await db.execute(stmt)
        perm = res.scalar_one_or_none()
        if perm is None:
            return False

        capability_name = perm.capability_name
        pattern = perm.resource_pattern
        scope = perm.scope

        await db.delete(perm)

        now = datetime.now(UTC)
        audit_entry = AuditLogModel(
            user_id=user_id,
            session_id="policy_session",
            agent_name="user",
            tool_name=capability_name,
            action_type="MODIFY",
            risk_level="MEDIUM",
            inputs={"permission_id": permission_id},
            outputs={"revoked": True},
            policy_verdict="REVOKED",
            event_type="PERMISSION_REVOKED",
            capability_name=capability_name,
            status="SUCCESS",
            details={
                "permission_id": permission_id,
                "capability_name": capability_name,
                "scope": scope,
                "pattern": pattern,
            },
            ip_address=ip_address,
            duration_ms=1.0,
            created_at=now,
            timestamp=now,
        )
        db.add(audit_entry)
        await db.commit()
        return True

    async def auto_expire_approvals(self, db: AsyncSession) -> int:
        """Transition expired pending approvals to EXPIRED status."""
        now = datetime.now(UTC)
        stmt = (
            update(ApprovalRequestModel)
            .where(
                ApprovalRequestModel.status == "PENDING",
                ApprovalRequestModel.expires_at.is_not(None),
                ApprovalRequestModel.expires_at < now,
            )
            .values(status="EXPIRED", resolved_at=now)
        )
        res = await db.execute(stmt)
        await db.commit()
        row_count = getattr(res, "rowcount", 0)
        return int(row_count if row_count is not None else 0)
