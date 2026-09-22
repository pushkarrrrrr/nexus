"""Unit and Integration Tests for NEXUS Policy Engine, Trust Model, and Audit Logging."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from packages.shared.nexus_shared.models import (
    ApprovalRequestModel,
    AuditLogModel,
    UserPermissionModel,
)
from packages.shared.nexus_shared.policy import (
    CapabilityRegistry,
    PolicyEngine,
    PolicyManager,
    match_resource_pattern,
    normalize_resource_target,
)
from services.api.nexus_api.database import get_session_factory, init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"policy_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def auth_user_a():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "full_name": "Policy User Alpha",
            },
        )
        assert reg.status_code == 201, reg.text
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        user_id = reg.json()["user"]["id"]
        yield {
            "client": client,
            "token": token,
            "user_id": user_id,
            "headers": {"Authorization": f"Bearer {token}"},
        }


@pytest.fixture
async def auth_user_b():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "full_name": "Policy User Beta",
            },
        )
        assert reg.status_code == 201, reg.text
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        user_id = reg.json()["user"]["id"]
        yield {
            "client": client,
            "token": token,
            "user_id": user_id,
            "headers": {"Authorization": f"Bearer {token}"},
        }


# ==============================================================================
# 1. Capability Registry & Pattern Matching Unit Tests
# ==============================================================================


def test_capability_registry_defaults():
    registry = CapabilityRegistry()
    assert registry.is_valid("filesystem.read") is True
    assert registry.is_valid("terminal.execute") is True
    assert registry.is_valid("system.configure") is True
    assert registry.is_valid("unknown.capability") is False

    assert registry.get_risk_level("filesystem.read") == "LOW"
    assert registry.get_risk_level("terminal.execute") == "HIGH"
    assert registry.get_risk_level("system.configure") == "CRITICAL"


def test_canonical_path_normalization():
    # Relative path normalization
    normalized = normalize_resource_target("./safe/../safe/file.txt")
    assert "/../" not in normalized
    assert normalized.endswith("/safe/file.txt")

    # Boundary check with traversal
    traversal = normalize_resource_target("/workspace/safe/../../etc/shadow")
    assert traversal.endswith("/etc/shadow")
    assert "safe" not in traversal


def test_match_resource_pattern():
    assert match_resource_pattern("/workspace/data/file.txt", "/workspace/data/*") is True
    assert match_resource_pattern("/workspace/data/sub/file.txt", "/workspace/data/*") is True
    assert match_resource_pattern("/workspace/secrets/keys.env", "/workspace/data/*") is False
    assert match_resource_pattern("anything", "*") is True


# ==============================================================================
# 2. Policy Engine Evaluation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_evaluate_unknown_capability_blocked(auth_user_a: dict[str, Any]):
    user_id = auth_user_a["user_id"]
    engine = PolicyEngine()
    session_factory = get_session_factory()

    async with session_factory() as db:
        decision = await engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="nonexistent.action",
            resource_target="/workspace/test",
        )
        assert decision.verdict == "BLOCKED"
        assert "Unknown capability" in decision.reason

        # Verify audit log recorded
        audit_res = await db.execute(
            select(AuditLogModel).where(
                AuditLogModel.user_id == user_id,
                AuditLogModel.event_type == "ACTION_BLOCKED",
            )
        )
        log = audit_res.scalar_one_or_none()
        assert log is not None
        assert log.status == "BLOCKED"


@pytest.mark.asyncio
async def test_evaluate_action_requiring_approval(auth_user_a: dict[str, Any]):
    user_id = auth_user_a["user_id"]
    engine = PolicyEngine()
    session_factory = get_session_factory()

    async with session_factory() as db:
        # High risk action without permission generates pending approval
        decision = await engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="terminal.execute",
            resource_target="/bin/bash",
            params={"command": "ls -la"},
        )
        assert decision.verdict == "REQUIRES_APPROVAL"
        assert decision.approval_id is not None
        assert decision.risk_level == "HIGH"

        # Verify approval request was created in DB
        appr_res = await db.execute(
            select(ApprovalRequestModel).where(ApprovalRequestModel.id == decision.approval_id)
        )
        approval = appr_res.scalar_one_or_none()
        assert approval is not None
        assert approval.status == "PENDING"
        assert approval.capability_name == "terminal.execute"
        assert approval.user_id == user_id


@pytest.mark.asyncio
async def test_evaluate_action_with_valid_permission(auth_user_a: dict[str, Any]):
    user_id = auth_user_a["user_id"]
    engine = PolicyEngine()
    session_factory = get_session_factory()

    async with session_factory() as db:
        # Grant a session permission
        perm = UserPermissionModel(
            user_id=user_id,
            capability_name="filesystem.read",
            scope="SESSION",
            resource_pattern="/workspace/docs/*",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        db.add(perm)
        await db.commit()

        # Target matching permission pattern is ALLOWED
        decision = await engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="filesystem.read",
            resource_target="/workspace/docs/readme.md",
        )
        assert decision.verdict == "ALLOWED"
        assert decision.matching_permission_id == perm.id

        # Target outside permission pattern requires approval
        outside_decision = await engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="filesystem.read",
            resource_target="/workspace/private/keys.txt",
        )
        assert outside_decision.verdict == "REQUIRES_APPROVAL"


@pytest.mark.asyncio
async def test_atomic_one_time_permission_consumption(auth_user_a: dict[str, Any]):
    """Safeguard: verify ONE_TIME permission cannot be reused (TOCTOU protection)."""
    user_id = auth_user_a["user_id"]
    engine = PolicyEngine()
    session_factory = get_session_factory()

    async with session_factory() as db:
        perm = UserPermissionModel(
            user_id=user_id,
            capability_name="filesystem.write",
            scope="ONE_TIME",
            resource_pattern="/workspace/output.txt",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        db.add(perm)
        await db.commit()

        # First evaluation should consume the permission and be ALLOWED
        decision_1 = await engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="filesystem.write",
            resource_target="/workspace/output.txt",
        )
        assert decision_1.verdict == "ALLOWED"

        # Permission should be deleted from DB
        perm_check = await db.execute(
            select(UserPermissionModel).where(UserPermissionModel.id == perm.id)
        )
        assert perm_check.scalar_one_or_none() is None

        # Second evaluation must now require a new approval
        decision_2 = await engine.evaluate_action(
            db=db,
            user_id=user_id,
            capability_name="filesystem.write",
            resource_target="/workspace/output.txt",
        )
        assert decision_2.verdict == "REQUIRES_APPROVAL"


# ==============================================================================
# 3. Approval Resolution & Safeguards Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_resolve_approval_with_session_and_standing(auth_user_a: dict[str, Any]):
    user_id = auth_user_a["user_id"]
    manager = PolicyManager()
    session_factory = get_session_factory()

    async with session_factory() as db:
        # 1. Resolve LOW-risk READ capability with STANDING scope -> Success
        appr_read = ApprovalRequestModel(
            user_id=user_id,
            capability_name="filesystem.read",
            action_category="READ",
            risk_level="LOW",
            reason="Read documentation",
            affected_resources=["/workspace/docs/*"],
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        db.add(appr_read)
        await db.commit()

        resolved_read = await manager.resolve_approval(
            db=db,
            user_id=user_id,
            approval_id=appr_read.id,
            decision="APPROVED",
            chosen_scope="STANDING",
        )
        assert resolved_read.status == "APPROVED"
        assert resolved_read.approved_scope == "STANDING"

        # Verify STANDING permission created with null expiry
        perm_res = await db.execute(
            select(UserPermissionModel).where(
                UserPermissionModel.user_id == user_id,
                UserPermissionModel.capability_name == "filesystem.read",
                UserPermissionModel.scope == "STANDING",
            )
        )
        standing_perm = perm_res.scalar_one_or_none()
        assert standing_perm is not None
        assert standing_perm.expires_at is None

        # 2. Attempt STANDING scope on HIGH-risk EXECUTE -> Must raise ValueError
        appr_exec = ApprovalRequestModel(
            user_id=user_id,
            capability_name="terminal.execute",
            action_category="EXECUTE",
            risk_level="HIGH",
            reason="Run bash shell",
            affected_resources=["/bin/sh"],
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        db.add(appr_exec)
        await db.commit()

        with pytest.raises(ValueError, match="strictly restricted to LOW-risk READ"):
            await manager.resolve_approval(
                db=db,
                user_id=user_id,
                approval_id=appr_exec.id,
                decision="APPROVED",
                chosen_scope="STANDING",
            )

        # 3. Resolve HIGH-risk with SESSION scope -> Success with TTL
        resolved_exec = await manager.resolve_approval(
            db=db,
            user_id=user_id,
            approval_id=appr_exec.id,
            decision="APPROVED",
            chosen_scope="SESSION",
            session_ttl_minutes=45,
        )
        assert resolved_exec.status == "APPROVED"
        assert resolved_exec.approved_scope == "SESSION"


@pytest.mark.asyncio
async def test_inline_expiration_enforcement(auth_user_a: dict[str, Any]):
    """Safeguard: expired approval must immediately transition to EXPIRED and reject."""
    user_id = auth_user_a["user_id"]
    manager = PolicyManager()
    session_factory = get_session_factory()

    async with session_factory() as db:
        expired_appr = ApprovalRequestModel(
            user_id=user_id,
            capability_name="filesystem.delete",
            action_category="DELETE",
            risk_level="HIGH",
            reason="Delete stale logs",
            affected_resources=["/tmp/logs"],
            expires_at=datetime.now(UTC) - timedelta(seconds=10),  # In the past
            status="PENDING",
        )
        db.add(expired_appr)
        await db.commit()

        with pytest.raises(ValueError, match="expired and cannot be resolved"):
            await manager.resolve_approval(
                db=db,
                user_id=user_id,
                approval_id=expired_appr.id,
                decision="APPROVED",
                chosen_scope="ONE_TIME",
            )

        # Verify status in database transitioned to EXPIRED
        await db.refresh(expired_appr)
        assert expired_appr.status == "EXPIRED"


# ==============================================================================
# 4. Append-Only Audit Ledger Verification Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_audit_log_immutable_append_only(auth_user_a: dict[str, Any]):
    """Constitution check: audit_logs prohibits UPDATE and DELETE mutations."""
    user_id = auth_user_a["user_id"]
    session_factory = get_session_factory()

    async with session_factory() as db:
        audit_log = AuditLogModel(
            user_id=user_id,
            session_id="test_session",
            agent_name="tester",
            tool_name="test_tool",
            action_type="READ",
            risk_level="LOW",
            event_type="POLICY_CHECK",
            capability_name="filesystem.read",
            status="SUCCESS",
            policy_verdict="ALLOWED",
            details={"test": True},
        )
        db.add(audit_log)
        await db.commit()
        await db.refresh(audit_log)

        # Attempt to mutate a field -> Must raise ValueError
        audit_log.policy_verdict = "MUTATED"
        with pytest.raises(ValueError, match="immutable and cannot be updated"):
            await db.commit()
        await db.rollback()

        # Attempt to delete the record -> Must raise ValueError
        await db.delete(audit_log)
        with pytest.raises(ValueError, match="append-only and cannot be deleted"):
            await db.commit()
        await db.rollback()


# ==============================================================================
# 5. Multi-Tenant Isolation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_multi_tenant_isolation_on_approvals_and_permissions(
    auth_user_a: dict[str, Any],
    auth_user_b: dict[str, Any],
):
    client_a = auth_user_a["client"]
    headers_a = auth_user_a["headers"]
    client_b = auth_user_b["client"]
    headers_b = auth_user_b["headers"]

    # User A triggers an evaluation that requires approval
    eval_res = await client_a.post(
        "/api/v1/policy/evaluate",
        json={
            "capability_name": "terminal.execute",
            "resource_target": "/bin/bash",
            "params": {"cmd": "echo alpha"},
        },
        headers=headers_a,
    )
    assert eval_res.status_code == 200
    approval_id_a = eval_res.json()["approval_id"]
    assert approval_id_a is not None

    # User B lists approvals -> Should NOT see User A's approval
    b_approvals = await client_b.get("/api/v1/policy/approvals", headers=headers_b)
    assert b_approvals.status_code == 200
    b_items = b_approvals.json()["items"]
    assert all(item["id"] != approval_id_a for item in b_items)

    # User B attempts to resolve User A's approval -> 400 or 404
    resolve_attempt = await client_b.post(
        f"/api/v1/policy/approvals/{approval_id_a}/resolve",
        json={"decision": "APPROVED", "chosen_scope": "ONE_TIME"},
        headers=headers_b,
    )
    assert resolve_attempt.status_code == 400
    assert "not found" in resolve_attempt.json()["detail"].lower()

    # User A resolves their own approval successfully
    resolve_success = await client_a.post(
        f"/api/v1/policy/approvals/{approval_id_a}/resolve",
        json={"decision": "APPROVED", "chosen_scope": "SESSION"},
        headers=headers_a,
    )
    assert resolve_success.status_code == 200
    assert resolve_success.json()["approval"]["status"] == "APPROVED"


# ==============================================================================
# 6. REST API Endpoint Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_policy_rest_endpoints(auth_user_a: dict[str, Any]):
    client = auth_user_a["client"]
    headers = auth_user_a["headers"]

    # 1. GET /capabilities
    caps_res = await client.get("/api/v1/policy/capabilities", headers=headers)
    assert caps_res.status_code == 200
    caps_data = caps_res.json()
    assert caps_data["total"] >= 10
    assert any(c["name"] == "filesystem.read" for c in caps_data["items"])

    # 2. POST /evaluate
    eval_res = await client.post(
        "/api/v1/policy/evaluate",
        json={
            "capability_name": "filesystem.delete",
            "resource_target": "/workspace/old_logs.txt",
        },
        headers=headers,
    )
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["verdict"] == "REQUIRES_APPROVAL"
    approval_id = eval_data["approval_id"]

    # 3. GET /approvals
    appr_res = await client.get("/api/v1/policy/approvals?status=PENDING", headers=headers)
    assert appr_res.status_code == 200
    appr_data = appr_res.json()
    assert any(a["id"] == approval_id for a in appr_data["items"])

    # 4. POST /approvals/{id}/resolve
    res_res = await client.post(
        f"/api/v1/policy/approvals/{approval_id}/resolve",
        json={"decision": "APPROVED", "chosen_scope": "ONE_TIME"},
        headers=headers,
    )
    assert res_res.status_code == 200
    assert res_res.json()["approval"]["status"] == "APPROVED"

    # 5. GET /permissions
    perm_res = await client.get("/api/v1/policy/permissions", headers=headers)
    assert perm_res.status_code == 200
    perms_data = perm_res.json()
    assert perms_data["total"] >= 1
    granted_perm_id = perms_data["items"][0]["id"]

    # 6. DELETE /permissions/{id}
    del_res = await client.delete(f"/api/v1/policy/permissions/{granted_perm_id}", headers=headers)
    assert del_res.status_code == 204

    # Verify permission was revoked
    perm_after = await client.get("/api/v1/policy/permissions", headers=headers)
    assert all(p["id"] != granted_perm_id for p in perm_after.json()["items"])

    # 7. GET /audit
    audit_res = await client.get("/api/v1/policy/audit", headers=headers)
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["total"] >= 1
    assert any(
        log["event_type"] in ("APPROVAL_REQUESTED", "APPROVAL_RESOLVED")
        for log in audit_data["items"]
    )
