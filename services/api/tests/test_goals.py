"""Integration tests for NEXUS Sessions and Goals Routes."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from services.api.nexus_api.database import init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"goal_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "GoalPassword123!", "full_name": "Goal Tester"},
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client, reg.json()["user"]


@pytest.mark.asyncio
async def test_sessions_crud_and_isolation(auth_client):
    client, user = auth_client

    # 1. Create session
    create_res = await client.post(
        "/api/v1/sessions",
        json={"title": "Interactive Dev Session", "metadata": {"ide": "cursor", "theme": "dark"}},
    )
    assert create_res.status_code == 201
    sess = create_res.json()
    assert sess["session_id"].startswith("sess_")
    assert sess["user_id"] == user["id"]
    assert sess["title"] == "Interactive Dev Session"
    assert sess["metadata"]["ide"] == "cursor"

    # 2. List sessions
    list_res = await client.get("/api/v1/sessions")
    assert list_res.status_code == 200
    assert any(s["session_id"] == sess["session_id"] for s in list_res.json())

    # 3. Get session by ID
    get_res = await client.get(f"/api/v1/sessions/{sess['session_id']}")
    assert get_res.status_code == 200
    assert get_res.json()["session_id"] == sess["session_id"]

    # 4. Delete session
    del_res = await client.delete(f"/api/v1/sessions/{sess['session_id']}")
    assert del_res.status_code == 204

    # Verify 404 after deletion
    get_del = await client.get(f"/api/v1/sessions/{sess['session_id']}")
    assert get_del.status_code == 404


@pytest.mark.asyncio
async def test_goal_creation_and_milestones(auth_client):
    client, user = auth_client

    payload = {
        "title": "Establish Automated Benchmarking",
        "description": "Decompose metrics into repeatable DAG pipelines",
        "category": "infrastructure",
        "milestones": [
            {"id": "m1", "title": "Configure Prometheus metrics", "completed": True},
            {"id": "m2", "title": "Implement Locust load scripts", "completed": False},
            {"id": "m3", "title": "Generate CI reports", "completed": False},
        ],
    }
    create_res = await client.post("/api/v1/goals", json=payload)
    assert create_res.status_code == 201
    goal = create_res.json()

    assert goal["id"].startswith("goal_")
    assert goal["user_id"] == user["id"]
    assert goal["title"] == "Establish Automated Benchmarking"
    assert goal["status"] == "active"
    assert goal["category"] == "infrastructure"
    assert len(goal["milestones"]) == 3
    # 1 of 3 completed = 33.3%
    assert goal["progress"] == 33.3


@pytest.mark.asyncio
async def test_goal_update_and_auto_completion(auth_client):
    client, _ = auth_client

    # Create goal with 2 milestones
    create_res = await client.post(
        "/api/v1/goals",
        json={
            "title": "Deploy to staging",
            "milestones": [
                {"id": "ms_1", "title": "Run migrations", "completed": False},
                {"id": "ms_2", "title": "Verify health checks", "completed": False},
            ],
        },
    )
    goal_id = create_res.json()["id"]

    # Update: Mark both completed
    patch_res = await client.patch(
        f"/api/v1/goals/{goal_id}",
        json={
            "milestones": [
                {"id": "ms_1", "title": "Run migrations", "completed": True},
                {"id": "ms_2", "title": "Verify health checks", "completed": True},
            ]
        },
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["progress"] == 100.0
    # Auto-completed since 100% reached
    assert updated["status"] == "completed"


@pytest.mark.asyncio
async def test_goals_list_and_filters(auth_client):
    client, _ = auth_client

    await client.post("/api/v1/goals", json={"title": "Goal Alpha", "category": "security"})
    g2 = await client.post("/api/v1/goals", json={"title": "Goal Beta", "category": "engineering"})
    # Pause goal beta
    await client.patch(f"/api/v1/goals/{g2.json()['id']}", json={"status": "paused"})

    # Filter by category
    sec_res = await client.get("/api/v1/goals?category=security")
    assert sec_res.status_code == 200
    assert all(g["category"] == "security" for g in sec_res.json())

    # Filter by status
    paused_res = await client.get("/api/v1/goals?status=paused")
    assert paused_res.status_code == 200
    assert all(g["status"] == "paused" for g in paused_res.json())


@pytest.mark.asyncio
async def test_goal_tenant_isolation():
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client_a,
        AsyncClient(transport=transport, base_url="http://test") as client_b,
    ):
        reg_a = await client_a.post(
            "/api/v1/auth/register",
            json={"email": random_email(), "password": "Password123!"},
        )
        client_a.headers["Authorization"] = f"Bearer {reg_a.json()['access_token']}"

        reg_b = await client_b.post(
            "/api/v1/auth/register",
            json={"email": random_email(), "password": "Password123!"},
        )
        client_b.headers["Authorization"] = f"Bearer {reg_b.json()['access_token']}"

        # User A creates a goal
        ga = await client_a.post("/api/v1/goals", json={"title": "Confidential Goal"})
        goal_id = ga.json()["id"]

        # User B cannot access or modify User A's goal
        assert (await client_b.get(f"/api/v1/goals/{goal_id}")).status_code == 404
        assert (
            await client_b.patch(f"/api/v1/goals/{goal_id}", json={"title": "Hijacked"})
        ).status_code == 404
        assert (await client_b.delete(f"/api/v1/goals/{goal_id}")).status_code == 404
