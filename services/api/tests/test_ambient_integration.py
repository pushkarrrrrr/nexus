"""Integration tests for Phase 12 Ambient NEXUS Desktop Layer."""

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from services.api.nexus_api.database import init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"ambient_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def auth_user() -> AsyncGenerator[dict[str, Any], None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "full_name": "Ambient Test Operator",
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


def test_ambient_websocket_surface_handshake():
    """Verify ambient desktop HUD connects via WebSocket and exchanges real-time telemetry."""
    client = TestClient(app)
    session_id = f"sess_ambient_{uuid.uuid4().hex[:8]}"

    with client.websocket_connect(
        f"/ws/nexus?client_surface=ambient&session_id={session_id}"
    ) as ws:
        # 1. Welcome event
        welcome = ws.receive_json()
        assert welcome["event_type"] == "dag.updated"
        assert welcome["session_id"] == session_id
        assert welcome["payload"]["status"] == "connected"

        # 2. Heartbeat / ping from ambient surface
        ping_event = {
            "event_type": "ambient.heartbeat",
            "session_id": session_id,
            "payload": {"client": "nexus-ambient", "version": "0.1.0"},
        }
        ws.send_text(json.dumps(ping_event))

        # 3. Acknowledged
        ack = ws.receive_json()
        assert ack["event_type"] == "audit.recorded"
        assert ack["payload"]["status"] == "acknowledged"


@pytest.mark.asyncio
async def test_system_status_ambient_surface():
    """Verify system readiness reflects Phase 12 ambient desktop support."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/system/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ready"
        assert data["phase"] in ("phase_12_ambient_desktop", "phase_14_autonomous_triggers")
        assert "ambient" in data["supported_surfaces"]


@pytest.mark.asyncio
async def test_ambient_surface_task_execution(auth_user: dict[str, Any]):
    """Verify task execution dispatched from ambient HUD with ambient client headers."""
    client = auth_user["client"]
    headers = dict(auth_user["headers"])
    headers["X-Client-Surface"] = "ambient"

    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    goal_payload = {
        "goal": "Analyze local memory context",
        "session_id": session_id,
        "context": {
            "app_name": "VS Code",
            "window_title": "test_ambient.py",
            "selected_text": "def test_ambient(): pass",
        },
    }

    res = await client.post(
        "/api/v1/agents/execute",
        headers=headers,
        json=goal_payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert "task_id" in data
    assert data["status"] in ("completed", "pending", "running")
