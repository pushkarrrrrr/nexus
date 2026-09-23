"""Comprehensive Unit and Integration Tests for Phase 14:
Autonomous Proactive Watchers, Event Triggers & Self-Healing Engine.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from packages.shared.nexus_shared.models import (
    ApprovalRequestModel,
    ProactiveTriggerModel,
    TriggerEventModel,
    UserModel,
)
from packages.shared.nexus_shared.policy.registry import get_capability_registry
from packages.shared.nexus_shared.proactive import (
    ProactiveTriggerEngine,
    RemediationCoordinator,
    SystemMetricsSnapshot,
    SystemWatcher,
    TriggerEvaluator,
)
from packages.shared.nexus_shared.tools.registry import get_tool_registry
from services.api.nexus_api.database import get_session_factory, init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"phase14_test_{uuid.uuid4().hex[:8]}@example.com"


async def create_test_user() -> tuple[dict[str, str], UserModel]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "StrongPassword123!", "full_name": "Phase 14 User"},
        )
        assert reg_res.status_code == 201
        data = reg_res.json()
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(UserModel).where(UserModel.id == data["user"]["id"])
            res = await session.execute(stmt)
            user = res.scalar_one()

        return headers, user


# ============================================================================
# 1. SystemWatcher & Host Telemetry Tests
# ============================================================================
def test_system_watcher_native_collection():
    watcher = SystemWatcher()
    snapshot = watcher.capture_metrics()

    assert isinstance(snapshot, SystemMetricsSnapshot)
    assert 0.0 <= snapshot.cpu_percent <= 100.0
    assert snapshot.disk_total_bytes >= 0
    assert snapshot.disk_percent >= 0.0
    assert snapshot.status in ("healthy", "degraded")


def test_system_watcher_mock_override():
    mock_snap = SystemMetricsSnapshot(
        cpu_percent=92.5,
        cpu_load_1m=4.5,
        memory_percent=88.0,
        disk_percent=91.0,
        status="degraded",
    )
    watcher = SystemWatcher(metrics_override=lambda: mock_snap)
    snap = watcher.capture_metrics()

    assert snap.cpu_percent == 92.5
    assert snap.status == "degraded"


# ============================================================================
# 2. TriggerEvaluator Rule Tests
# ============================================================================
def test_evaluator_threshold_conditions():
    evaluator = TriggerEvaluator()
    trigger = ProactiveTriggerModel(
        user_id="usr_test",
        name="CPU Alarm",
        trigger_type="threshold",
        condition={"metric_name": "cpu_percent", "operator": ">", "threshold_value": 80.0},
        action_capability="remediation.execute_fix",
        cooldown_seconds=300,
        is_active=True,
    )

    # 1. Below threshold -> Not triggered
    metrics_low = SystemMetricsSnapshot(cpu_percent=45.0)
    triggered, reason, _ = evaluator.evaluate(trigger, metrics=metrics_low)
    assert not triggered

    # 2. Above threshold -> Triggered
    metrics_high = SystemMetricsSnapshot(cpu_percent=89.2)
    triggered, reason, obs = evaluator.evaluate(trigger, metrics=metrics_high)
    assert triggered
    assert "89.2" in reason
    assert obs["current_value"] == 89.2


def test_evaluator_cooldown_enforcement():
    evaluator = TriggerEvaluator()
    now = datetime.now(UTC)
    trigger = ProactiveTriggerModel(
        user_id="usr_test",
        name="Rapid Alarm",
        trigger_type="threshold",
        condition={"metric_name": "cpu_percent", "operator": ">", "threshold_value": 50.0},
        action_capability="remediation.execute_fix",
        cooldown_seconds=300,
        last_triggered_at=now - timedelta(seconds=100),  # 100s ago, cooldown 300s
        is_active=True,
    )

    metrics = SystemMetricsSnapshot(cpu_percent=90.0)
    triggered, reason, _obs = evaluator.evaluate(trigger, metrics=metrics, now=now)
    assert not triggered
    assert "Cooldown active" in reason


def test_evaluator_schedule_and_inactive():
    evaluator = TriggerEvaluator()
    trigger = ProactiveTriggerModel(
        user_id="usr_test",
        name="Scheduled Trigger",
        trigger_type="schedule",
        condition={"schedule_interval_sec": 60},
        action_capability="watcher.get_system_metrics",
        is_active=False,
    )
    triggered, reason, _ = evaluator.evaluate(trigger)
    assert not triggered
    assert "inactive" in reason.lower()

    # Re-enable
    trigger.is_active = True
    triggered, reason, _ = evaluator.evaluate(trigger)
    assert triggered


# ============================================================================
# 3. Policy & Tool Registry Registration Tests
# ============================================================================
def test_phase14_capabilities_registered():
    cap_reg = get_capability_registry()

    watcher_metrics_cap = cap_reg.get("watcher.get_system_metrics")
    assert watcher_metrics_cap is not None
    assert watcher_metrics_cap.category == "SYSTEM_INFO"
    assert watcher_metrics_cap.default_risk_level == "LOW"

    fix_cap = cap_reg.get("remediation.execute_fix")
    assert fix_cap is not None
    assert fix_cap.category == "SYSTEM_CONTROL"
    assert fix_cap.default_risk_level == "HIGH"

    recovery_cap = cap_reg.get("remediation.trigger_recovery")
    assert recovery_cap is not None
    assert recovery_cap.default_risk_level == "HIGH"


def test_phase14_tools_registered():
    tool_reg = get_tool_registry()

    assert tool_reg.get("watcher.get_system_metrics") is not None
    assert tool_reg.get("watcher.inspect_events") is not None
    assert tool_reg.get("trigger.create_rule") is not None
    assert tool_reg.get("trigger.list_rules") is not None
    assert tool_reg.get("remediation.execute_fix") is not None
    assert tool_reg.get("remediation.trigger_recovery") is not None


# ============================================================================
# 4. Strict Safety Gating & Remediation Tests
# ============================================================================
@pytest.mark.asyncio
async def test_remediation_safety_gating_high_risk():
    """HIGH risk proactive action must HALT, create ApprovalRequestModel, and notify client."""
    _, user = await create_test_user()
    factory = get_session_factory()

    mock_broadcaster = AsyncMock()
    coordinator = RemediationCoordinator(event_broadcaster=mock_broadcaster)

    async with factory() as session:
        trigger = ProactiveTriggerModel(
            user_id=user.id,
            name="Critical Memory Guard",
            trigger_type="threshold",
            condition={"metric_name": "memory_percent", "operator": ">", "threshold_value": 85.0},
            action_capability="remediation.execute_fix",
            action_params={"fix_type": "clear_cache", "target": "system_cache"},
            cooldown_seconds=300,
            is_active=True,
        )
        session.add(trigger)
        await session.commit()
        await session.refresh(trigger)

        result = await coordinator.handle_evaluation_result(
            session=session,
            trigger=trigger,
            reason="Memory exceeded 85%",
            observed_data={"memory_percent": 91.2},
        )

        assert result.triggered is True
        assert result.requires_approval is True
        assert result.status == "awaiting_approval"
        assert result.approval_id is not None

        # Verify ApprovalRequestModel created in DB
        stmt_appr = select(ApprovalRequestModel).where(
            ApprovalRequestModel.id == result.approval_id
        )
        appr_res = await session.execute(stmt_appr)
        appr = appr_res.scalar_one()
        assert appr.risk_level == "HIGH"
        assert appr.status == "PENDING"
        assert appr.user_id == user.id

        # Verify TriggerEventModel created in DB
        stmt_evt = select(TriggerEventModel).where(
            TriggerEventModel.approval_id == result.approval_id
        )
        evt_res = await session.execute(stmt_evt)
        evt = evt_res.scalar_one()
        assert evt.status == "awaiting_approval"

        # Verify WebSocket broadcaster was called
        assert mock_broadcaster.call_count >= 1
        event_types = [call[0][0] for call in mock_broadcaster.call_args_list]
        assert "approval_required" in event_types


@pytest.mark.asyncio
async def test_remediation_autonomous_execution_low_risk():
    """LOW risk proactive action runs autonomously without creating approval blocks."""
    _, user = await create_test_user()
    factory = get_session_factory()

    coordinator = RemediationCoordinator()

    async with factory() as session:
        trigger = ProactiveTriggerModel(
            user_id=user.id,
            name="Telemetry Poller",
            trigger_type="schedule",
            condition={"schedule_interval_sec": 30},
            action_capability="watcher.get_system_metrics",
            action_params={},
            cooldown_seconds=30,
            is_active=True,
        )
        session.add(trigger)
        await session.commit()
        await session.refresh(trigger)

        result = await coordinator.handle_evaluation_result(
            session=session,
            trigger=trigger,
            reason="Schedule interval elapsed",
            observed_data={"interval": 30},
        )

        assert result.triggered is True
        assert result.requires_approval is False
        assert result.status == "executed"
        assert result.approval_id is None


# ============================================================================
# 5. ProactiveTriggerEngine Background Worker Lifecycle Tests
# ============================================================================
@pytest.mark.asyncio
async def test_proactive_engine_lifecycle_cancellation():
    engine = ProactiveTriggerEngine(poll_interval_sec=0.1)
    await engine.start()
    assert engine._running is True
    assert engine._task is not None

    # Wait brief moment for loop to execute
    await asyncio.sleep(0.15)

    # Stop gracefully
    await engine.stop()
    assert engine._running is False
    assert engine._task is None


# ============================================================================
# 6. FastAPI REST Endpoints Tests
# ============================================================================
@pytest.mark.asyncio
async def test_api_watcher_metrics():
    headers, _ = await create_test_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/watchers/metrics", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "cpu_percent" in data
        assert "disk_percent" in data
        assert "status" in data


@pytest.mark.asyncio
async def test_api_trigger_crud_and_evaluate():
    headers, _user = await create_test_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Trigger
        create_res = await client.post(
            "/api/v1/triggers",
            headers=headers,
            json={
                "name": "Disk Space Sentinel",
                "trigger_type": "threshold",
                "condition": {
                    "metric_name": "disk_percent",
                    "operator": ">",
                    "threshold_value": 75.0,
                },
                "action_capability": "remediation.execute_fix",
                "action_params": {"fix_type": "clear_cache", "target": "disk"},
                "cooldown_seconds": 120,
                "is_active": True,
            },
        )
        assert create_res.status_code == 201
        created = create_res.json()
        trigger_id = created["id"]
        assert created["name"] == "Disk Space Sentinel"

        # 2. Get Trigger
        get_res = await client.get(f"/api/v1/triggers/{trigger_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["id"] == trigger_id

        # 3. List Triggers
        list_res = await client.get("/api/v1/triggers", headers=headers)
        assert list_res.status_code == 200
        triggers_list = list_res.json()
        assert any(t["id"] == trigger_id for t in triggers_list)

        # 4. Toggle Trigger
        toggle_res = await client.patch(f"/api/v1/triggers/{trigger_id}/toggle", headers=headers)
        assert toggle_res.status_code == 200
        assert toggle_res.json()["is_active"] is False

        # Toggle back
        await client.patch(f"/api/v1/triggers/{trigger_id}/toggle", headers=headers)

        # 5. Evaluate On-Demand
        eval_res = await client.post(
            f"/api/v1/triggers/evaluate?trigger_id={trigger_id}",
            headers=headers,
        )
        assert eval_res.status_code == 200
        results = eval_res.json()
        assert len(results) == 1

        # 6. List Events
        events_res = await client.get("/api/v1/triggers/events", headers=headers)
        assert events_res.status_code == 200
        assert isinstance(events_res.json(), list)

        # 7. Delete Trigger
        del_res = await client.delete(f"/api/v1/triggers/{trigger_id}", headers=headers)
        assert del_res.status_code == 204

        # 8. Verify Deleted
        get_after = await client.get(f"/api/v1/triggers/{trigger_id}", headers=headers)
        assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_system_status_phase14():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/system/status")
        assert res.status_code == 200
        data = res.json()
        assert data["phase"] == "phase_14_autonomous_triggers"
        assert "ambient" in data["supported_surfaces"]
        assert "dashboard" in data["supported_surfaces"]
