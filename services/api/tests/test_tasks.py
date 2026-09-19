"""Integration tests for NEXUS Task Engine and Orchestration Routes."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from services.api.nexus_api.database import init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"task_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "TaskPassword123!", "full_name": "Task Tester"},
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client, reg.json()["user"]


@pytest.mark.asyncio
async def test_create_task_dag_with_nodes(auth_client):
    client, user = auth_client
    payload = {
        "goal": "Synthesize micro-benchmarks",
        "execution_metadata": {"priority": "high", "timeout_sec": 300},
        "nodes": [
            {
                "name": "Parse input corpus",
                "agent": "ingestor",
                "tool": "file_reader",
                "input": {"path": "/workspace/data"},
                "dependencies": [],
            },
            {
                "name": "Run benchmark suite",
                "agent": "executor",
                "tool": "terminal_runner",
                "input": {"cmd": "pytest benchmarks/"},
                "dependencies": ["Parse input corpus"],
            },
        ],
    }
    res = await client.post("/api/v1/tasks", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["dag_id"].startswith("dag_")
    assert data["goal"] == "Synthesize micro-benchmarks"
    assert data["status"] == "pending"
    assert data["user_id"] == user["id"]
    assert len(data["nodes"]) == 2
    assert data["nodes"][0]["name"] == "Parse input corpus"
    assert data["nodes"][0]["status"] == "pending"
    assert data["nodes"][1]["name"] == "Run benchmark suite"
    assert data["execution_metadata"]["priority"] == "high"


@pytest.mark.asyncio
async def test_list_tasks_and_filter(auth_client):
    client, _ = auth_client
    # Create 2 tasks
    await client.post("/api/v1/tasks", json={"goal": "Task One"})
    t2_res = await client.post("/api/v1/tasks", json={"goal": "Task Two"})
    t2_id = t2_res.json()["dag_id"]

    # Transition t2 to executing
    await client.post(
        f"/api/v1/tasks/{t2_id}/transition",
        json={"to_state": "planning", "reason": "Planning started"},
    )
    await client.post(
        f"/api/v1/tasks/{t2_id}/transition",
        json={"to_state": "executing", "reason": "Execution underway"},
    )

    # List all
    all_res = await client.get("/api/v1/tasks")
    assert all_res.status_code == 200
    assert len(all_res.json()) >= 2

    # Filter by status
    exec_res = await client.get("/api/v1/tasks?status=executing")
    assert exec_res.status_code == 200
    assert all(t["status"] == "executing" for t in exec_res.json())

    pend_res = await client.get("/api/v1/tasks?status=pending")
    assert pend_res.status_code == 200
    assert all(t["status"] == "pending" for t in pend_res.json())


@pytest.mark.asyncio
async def test_get_task_by_id(auth_client):
    client, _ = auth_client
    create_res = await client.post("/api/v1/tasks", json={"goal": "Inspect memory leak"})
    task_id = create_res.json()["dag_id"]

    get_res = await client.get(f"/api/v1/tasks/{task_id}")
    assert get_res.status_code == 200
    assert get_res.json()["dag_id"] == task_id
    assert get_res.json()["goal"] == "Inspect memory leak"


@pytest.mark.asyncio
async def test_add_subtask_step(auth_client):
    client, _ = auth_client
    task_res = await client.post("/api/v1/tasks", json={"goal": "Multi-step pipeline"})
    task_id = task_res.json()["dag_id"]

    step_payload = {
        "name": "Audit file integrity",
        "agent": "security_agent",
        "tool": "checksum_verifier",
        "input": {"target": "main.py"},
        "dependencies": [],
    }
    step_res = await client.post(f"/api/v1/tasks/{task_id}/steps", json=step_payload)
    assert step_res.status_code == 201
    step_data = step_res.json()
    assert step_data["id"].startswith("step_")
    assert step_data["name"] == "Audit file integrity"
    assert step_data["status"] == "pending"

    # Verify task now contains the node
    updated_task = await client.get(f"/api/v1/tasks/{task_id}")
    assert len(updated_task.json()["nodes"]) == 1


@pytest.mark.asyncio
async def test_task_state_machine_valid_transitions(auth_client):
    client, _ = auth_client
    task_res = await client.post("/api/v1/tasks", json={"goal": "Full state flow"})
    task_id = task_res.json()["dag_id"]

    # PENDING -> PLANNING
    r1 = await client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"to_state": "planning", "reason": "Decomposing task"},
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "planning"

    # PLANNING -> EXECUTING
    r2 = await client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"to_state": "executing", "reason": "Executing steps"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "executing"

    # EXECUTING -> OBSERVING
    r3 = await client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"to_state": "observing", "reason": "Observing execution feedback"},
    )
    assert r3.status_code == 200
    assert r3.json()["status"] == "observing"

    # OBSERVING -> COMPLETED
    r4 = await client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"to_state": "completed", "reason": "All criteria met"},
    )
    assert r4.status_code == 200
    assert r4.json()["status"] == "completed"
    assert r4.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_task_state_machine_invalid_transition_rejected(auth_client):
    client, _ = auth_client
    task_res = await client.post("/api/v1/tasks", json={"goal": "Invalid transition test"})
    task_id = task_res.json()["dag_id"]

    # Try to jump from PENDING straight to COMPLETED (not allowed)
    invalid_res = await client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"to_state": "completed"},
    )
    assert invalid_res.status_code == 400
    assert "Invalid transition" in invalid_res.json()["detail"]


@pytest.mark.asyncio
async def test_transition_from_terminal_state_rejected(auth_client):
    client, _ = auth_client
    task_res = await client.post("/api/v1/tasks", json={"goal": "Terminal lock test"})
    task_id = task_res.json()["dag_id"]

    # Complete the task
    await client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"to_state": "planning"},
    )
    await client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"to_state": "executing"},
    )
    await client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"to_state": "completed"},
    )

    # Attempt to transition back to planning
    blocked_res = await client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"to_state": "planning"},
    )
    assert blocked_res.status_code == 400
    assert "Cannot transition from terminal state" in blocked_res.json()["detail"]


@pytest.mark.asyncio
async def test_step_state_transition_and_timestamps(auth_client):
    client, _ = auth_client
    task_res = await client.post(
        "/api/v1/tasks",
        json={
            "goal": "Step transition test",
            "nodes": [{"name": "Step Alpha", "agent": "worker"}],
        },
    )
    task = task_res.json()
    step_id = task["nodes"][0]["id"]

    # Transition step to executing
    step_exec = await client.post(
        f"/api/v1/tasks/{task['dag_id']}/steps/{step_id}/transition",
        json={"to_state": "executing"},
    )
    assert step_exec.status_code == 200
    exec_data = step_exec.json()
    assert exec_data["status"] == "executing"
    assert exec_data["started_at"] is not None

    # Transition step to completed
    step_comp = await client.post(
        f"/api/v1/tasks/{task['dag_id']}/steps/{step_id}/transition",
        json={"to_state": "completed", "result": {"output": "success"}},
    )
    assert step_comp.status_code == 200
    comp_data = step_comp.json()
    assert comp_data["status"] == "completed"
    assert comp_data["completed_at"] is not None
    assert comp_data["result"] == {"output": "success"}


@pytest.mark.asyncio
async def test_cascading_cancellation(auth_client):
    client, _ = auth_client
    # Create DAG with 3 subtasks: 1 already completed, 1 executing, 1 pending
    task_res = await client.post(
        "/api/v1/tasks",
        json={
            "goal": "Cascading cancellation test",
            "nodes": [
                {"name": "Done step", "agent": "worker"},
                {"name": "Running step", "agent": "worker"},
                {"name": "Queued step", "agent": "worker"},
            ],
        },
    )
    task = task_res.json()
    dag_id = task["dag_id"]
    n0_id = task["nodes"][0]["id"]
    n1_id = task["nodes"][1]["id"]
    n2_id = task["nodes"][2]["id"]

    # Step 0 -> completed
    await client.post(
        f"/api/v1/tasks/{dag_id}/steps/{n0_id}/transition",
        json={"to_state": "executing"},
    )
    await client.post(
        f"/api/v1/tasks/{dag_id}/steps/{n0_id}/transition",
        json={"to_state": "completed"},
    )

    # Step 1 -> executing
    await client.post(
        f"/api/v1/tasks/{dag_id}/steps/{n1_id}/transition",
        json={"to_state": "executing"},
    )

    # Cancel the task
    cancel_res = await client.post(
        f"/api/v1/tasks/{dag_id}/cancel",
        json={"reason": "Emergency stop invoked by user"},
    )
    assert cancel_res.status_code == 200
    cancelled_dag = cancel_res.json()

    assert cancelled_dag["status"] == "cancelled"
    assert cancelled_dag["completed_at"] is not None

    nodes_by_id = {n["id"]: n for n in cancelled_dag["nodes"]}
    # Node 0 remains completed
    assert nodes_by_id[n0_id]["status"] == "completed"
    # Node 1 was executing, now cancelled
    assert nodes_by_id[n1_id]["status"] == "cancelled"
    assert nodes_by_id[n1_id]["completed_at"] is not None
    # Node 2 was pending, now cancelled
    assert nodes_by_id[n2_id]["status"] == "cancelled"
    assert nodes_by_id[n2_id]["completed_at"] is not None


@pytest.mark.asyncio
async def test_task_timeline_events(auth_client):
    client, _ = auth_client
    task_res = await client.post(
        "/api/v1/tasks",
        json={
            "goal": "Audit timeline verification",
            "nodes": [{"name": "Step A", "agent": "worker"}],
        },
    )
    dag_id = task_res.json()["dag_id"]
    step_id = task_res.json()["nodes"][0]["id"]

    # Step transition
    await client.post(
        f"/api/v1/tasks/{dag_id}/steps/{step_id}/transition",
        json={"to_state": "executing"},
    )

    # Task transition
    await client.post(
        f"/api/v1/tasks/{dag_id}/transition",
        json={"to_state": "planning", "reason": "Refining sub-DAG"},
    )

    # Cancel
    await client.post(
        f"/api/v1/tasks/{dag_id}/cancel",
        json={"reason": "Cancelled for timeline audit"},
    )

    timeline_res = await client.get(f"/api/v1/tasks/{dag_id}/timeline")
    assert timeline_res.status_code == 200
    timeline = timeline_res.json()

    assert timeline["dag_id"] == dag_id
    assert timeline["total_events"] >= 4
    event_types = [e["event_type"] for e in timeline["events"]]
    assert "dag_created" in event_types
    assert "node_state_transition" in event_types
    assert "state_transition" in event_types
    assert "task_cancelled" in event_types


@pytest.mark.asyncio
async def test_task_tenant_isolation():
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client_a,
        AsyncClient(transport=transport, base_url="http://test") as client_b,
    ):
        # Register user A
        reg_a = await client_a.post(
            "/api/v1/auth/register",
            json={"email": random_email(), "password": "Password123!"},
        )
        client_a.headers["Authorization"] = f"Bearer {reg_a.json()['access_token']}"

        # Register user B
        reg_b = await client_b.post(
            "/api/v1/auth/register",
            json={"email": random_email(), "password": "Password123!"},
        )
        client_b.headers["Authorization"] = f"Bearer {reg_b.json()['access_token']}"

        # User A creates a task
        res_a = await client_a.post("/api/v1/tasks", json={"goal": "User A secret task"})
        task_id = res_a.json()["dag_id"]

        # User B cannot get task A
        get_b = await client_b.get(f"/api/v1/tasks/{task_id}")
        assert get_b.status_code == 404

        # User B cannot cancel task A
        cancel_b = await client_b.post(
            f"/api/v1/tasks/{task_id}/cancel", json={"reason": "Malicious cancel"}
        )
        assert cancel_b.status_code == 404

        # User B cannot get timeline of task A
        time_b = await client_b.get(f"/api/v1/tasks/{task_id}/timeline")
        assert time_b.status_code == 404
