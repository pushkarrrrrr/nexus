"""Integration and Unit Tests for Phase 8: Multi-Agent Orchestrator and Planning.

Covers:
- Agent roster endpoint with specialized agent definitions.
- Structured goal decomposition into verifiable execution plans.
- End-to-end multi-agent execution pipeline through Orchestrator.
- Explicit step dependency resolution and downstream skipping on failure.
- Failure recovery replanning capped at maximum replan iterations.
- Clean task cancellation halting running execution loops.
- Strict multi-tenant isolation on execution plans and steps.
"""

import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from packages.shared.nexus_shared.agents import (
    AgentStepResult,
    BaseAgent,
    get_orchestrator_agent,
)
from packages.shared.nexus_shared.models import (
    ExecutionPlanModel,
    PlanStepModel,
    SessionModel,
    TaskDAGModel,
    generate_uuid,
)
from packages.types.nexus_types.schemas import (
    PlanStatus,
    PlanStep,
    PlanStepStatus,
    TaskStatus,
)
from services.api.nexus_api.database import get_session_factory, init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"agent_test_{uuid.uuid4().hex[:8]}@example.com"


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
                "full_name": "Orchestrator User Alpha",
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
                "full_name": "Orchestrator User Beta",
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


@pytest.mark.asyncio
async def test_agent_roster_endpoint(auth_user_a: dict[str, Any]) -> None:
    """Test retrieving active agent roster."""
    client = auth_user_a["client"]
    headers = auth_user_a["headers"]

    res = await client.get("/api/v1/agents/roster", headers=headers)
    assert res.status_code == 200, res.text
    roster = res.json()
    assert len(roster) >= 4

    agent_types = [a["agent_type"] for a in roster]
    assert "orchestrator" in agent_types
    assert "planning" in agent_types
    assert "research" in agent_types
    assert "document" in agent_types


@pytest.mark.asyncio
async def test_generate_structured_plan() -> None:
    """Test planning agent goal decomposition into structured PlanSteps."""
    orchestrator = get_orchestrator_agent()
    steps = await orchestrator.planning_agent.generate_steps(
        goal="Audit PostgreSQL security configuration and prepare compliance report",
        context={"environment": "production"},
    )

    assert len(steps) >= 2
    for i, step in enumerate(steps):
        assert step.index == i
        assert step.id
        assert step.description
        assert step.assigned_agent in ("orchestrator", "planning", "research", "document")
        if i > 0:
            # Chained dependency verification
            assert len(step.dependencies) > 0


@pytest.mark.asyncio
async def test_orchestrator_end_to_end_execution(auth_user_a: dict[str, Any]) -> None:
    """Test submitting goal to /api/v1/agents/execute and end-to-end multi-agent execution."""
    client = auth_user_a["client"]
    headers = auth_user_a["headers"]

    payload = {
        "goal": "Research graph database models and summarize integration steps",
        "auto_run": True,
        "context": {"priority": "high"},
    }

    res = await client.post("/api/v1/agents/execute", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["task_id"]
    assert data["status"] == "completed"
    assert data["final_response"]
    assert len(data["messages"]) > 0

    plan = data["plan"]
    assert len(plan["steps"]) >= 2
    for step in plan["steps"]:
        assert step["status"] == "completed"
        assert step["result"] is not None

    # Verify plan retrieval via GET /api/v1/agents/plans/{task_id}
    plan_res = await client.get(f"/api/v1/agents/plans/{data['task_id']}", headers=headers)
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert plan_data["id"] == plan["id"]
    assert plan_data["status"] == "completed"


@pytest.mark.asyncio
async def test_dependency_resolution_and_downstream_skipping(auth_user_a: dict[str, Any]) -> None:
    """Test that failed dependencies properly mark downstream dependent steps as skipped."""
    user_id = auth_user_a["user_id"]
    orchestrator = get_orchestrator_agent()

    async with get_session_factory()() as db:
        # Create Session & TaskDAG
        session = SessionModel(
            id=generate_uuid("sess"),
            user_id=user_id,
            surface="dashboard",
            title="Dependency Test Session",
            os_context={},
        )
        db.add(session)
        await db.commit()

        task = TaskDAGModel(
            id=generate_uuid("dag"),
            user_id=user_id,
            session_id=session.id,
            goal="Dependency test goal",
            status=TaskStatus.PLANNING.value,
        )
        db.add(task)
        await db.commit()

        # Create Plan with 2 steps where step 1 depends on step 0
        plan = ExecutionPlanModel(
            id=generate_uuid("plan"),
            task_id=task.id,
            user_id=user_id,
            goal="Dependency failure pipeline",
            status=PlanStatus.CREATED.value,
            max_replans=0,  # disable replan for deterministic skip test
        )
        db.add(plan)
        await db.flush()

        s0_id = generate_uuid("pstep")
        s1_id = generate_uuid("pstep")
        step_0 = PlanStepModel(
            id=s0_id,
            plan_id=plan.id,
            index=0,
            description="Failing initial step",
            assigned_agent="custom_fail",
            dependencies=[],
            status=PlanStepStatus.PENDING.value,
            max_retries=0,
        )
        step_1 = PlanStepModel(
            id=s1_id,
            plan_id=plan.id,
            index=1,
            description="Downstream dependent step",
            assigned_agent="orchestrator",
            dependencies=[s0_id],
            status=PlanStepStatus.PENDING.value,
        )
        db.add_all([step_0, step_1])
        await db.commit()

        # Mock a failing custom agent
        class FailingAgent(BaseAgent):
            async def run(
                self, step: PlanStep, context: Any, user_id: str, db: Any
            ) -> AgentStepResult:
                return AgentStepResult(success=False, error_message="Simulated root failure")

        orchestrator._sub_agents["custom_fail"] = FailingAgent(
            agent_type="custom_fail",
            name="Failing Agent",
            description="Agent that fails",
        )

        # Execute
        executed_plan, _, _ = await orchestrator.execute_plan(
            plan_id=plan.id,
            user_id=user_id,
            db=db,
        )

        assert executed_plan.status == PlanStatus.FAILED.value

        # Verify step 0 failed and step 1 was skipped
        steps_q = await db.execute(
            select(PlanStepModel)
            .where(PlanStepModel.plan_id == plan.id)
            .order_by(PlanStepModel.index.asc())
        )
        steps = list(steps_q.scalars().all())
        assert steps[0].status == PlanStepStatus.FAILED.value
        assert steps[1].status == PlanStepStatus.SKIPPED.value
        assert "Upstream dependency" in str(steps[1].error_message)


@pytest.mark.asyncio
async def test_step_failure_and_replanning(auth_user_a: dict[str, Any]) -> None:
    """Test that a step failure triggers recovery replan up to max_replans."""
    user_id = auth_user_a["user_id"]
    orchestrator = get_orchestrator_agent()

    async with get_session_factory()() as db:
        session = SessionModel(
            id=generate_uuid("sess"),
            user_id=user_id,
            surface="dashboard",
            title="Replan Test Session",
            os_context={},
        )
        db.add(session)
        await db.commit()

        task = TaskDAGModel(
            id=generate_uuid("dag"),
            user_id=user_id,
            session_id=session.id,
            goal="Replan test goal",
            status=TaskStatus.PLANNING.value,
        )
        db.add(task)
        await db.commit()

        plan = ExecutionPlanModel(
            id=generate_uuid("plan"),
            task_id=task.id,
            user_id=user_id,
            goal="Replan pipeline",
            status=PlanStatus.CREATED.value,
            max_replans=2,
            replan_count=0,
        )
        db.add(plan)
        await db.flush()

        step_fail = PlanStepModel(
            id=generate_uuid("pstep"),
            plan_id=plan.id,
            index=0,
            description="Transient fail step",
            assigned_agent="transient_agent",
            dependencies=[],
            status=PlanStepStatus.PENDING.value,
            max_retries=0,
        )
        db.add(step_fail)
        await db.commit()

        # Transient agent fails on first call, then replan adds recovery step handled by orchestrator
        class TransientAgent(BaseAgent):
            async def run(
                self, step: PlanStep, context: Any, user_id: str, db: Any
            ) -> AgentStepResult:
                return AgentStepResult(success=False, error_message="Transient network error")

        orchestrator._sub_agents["transient_agent"] = TransientAgent(
            agent_type="transient_agent",
            name="Transient Agent",
            description="Agent that fails",
        )

        executed_plan, _final_answer, _ = await orchestrator.execute_plan(
            plan_id=plan.id,
            user_id=user_id,
            db=db,
        )

        # Plan should have replanned once
        assert executed_plan.replan_count >= 1

        # Check that recovery step was generated and executed
        steps_q = await db.execute(
            select(PlanStepModel)
            .where(PlanStepModel.plan_id == plan.id)
            .order_by(PlanStepModel.index.asc())
        )
        steps = list(steps_q.scalars().all())
        assert len(steps) >= 2
        assert steps[0].status == PlanStepStatus.FAILED.value
        assert steps[1].status == PlanStepStatus.COMPLETED.value
        assert "Recovery" in steps[1].description


@pytest.mark.asyncio
async def test_cancellation_halts_execution(auth_user_a: dict[str, Any]) -> None:
    """Test that cancelling a task halts plan execution immediately."""
    user_id = auth_user_a["user_id"]
    orchestrator = get_orchestrator_agent()

    async with get_session_factory()() as db:
        session = SessionModel(
            id=generate_uuid("sess"),
            user_id=user_id,
            surface="dashboard",
            title="Cancel Test Session",
            os_context={},
        )
        db.add(session)
        await db.commit()

        task = TaskDAGModel(
            id=generate_uuid("dag"),
            user_id=user_id,
            session_id=session.id,
            goal="Cancellation target goal",
            status=TaskStatus.CANCELLED.value,  # Already cancelled before run
        )
        db.add(task)
        await db.commit()

        plan = ExecutionPlanModel(
            id=generate_uuid("plan"),
            task_id=task.id,
            user_id=user_id,
            goal="Cancellation pipeline",
            status=PlanStatus.CANCELLED.value,
        )
        db.add(plan)
        await db.flush()

        step_0 = PlanStepModel(
            id=generate_uuid("pstep"),
            plan_id=plan.id,
            index=0,
            description="Step that should not run",
            assigned_agent="orchestrator",
            status=PlanStepStatus.PENDING.value,
        )
        db.add(step_0)
        await db.commit()

        executed_plan, answer, _ = await orchestrator.execute_plan(
            plan_id=plan.id,
            user_id=user_id,
            db=db,
        )

        assert executed_plan.status == PlanStatus.CANCELLED.value
        assert answer is not None and "cancelled" in answer.lower()

        # Step 0 should be skipped
        await db.refresh(step_0)
        assert step_0.status == PlanStepStatus.SKIPPED.value


@pytest.mark.asyncio
async def test_multi_tenant_isolation_on_plans(
    auth_user_a: dict[str, Any],
    auth_user_b: dict[str, Any],
) -> None:
    """Test that User B cannot view or replan User A's execution plan."""
    client_a = auth_user_a["client"]
    headers_a = auth_user_a["headers"]
    client_b = auth_user_b["client"]
    headers_b = auth_user_b["headers"]

    # User A creates execution plan
    exec_res = await client_a.post(
        "/api/v1/agents/execute",
        json={"goal": "User A secret plan"},
        headers=headers_a,
    )
    assert exec_res.status_code == 200
    task_id_a = exec_res.json()["task_id"]
    plan_id_a = exec_res.json()["plan"]["id"]

    # User B attempts to access User A's plan via task ID -> 404
    cross_res = await client_b.get(f"/api/v1/agents/plans/{task_id_a}", headers=headers_b)
    assert cross_res.status_code == 404

    # User B attempts to trigger replan on User A's plan -> 404
    cross_replan = await client_b.post(
        f"/api/v1/agents/plans/{plan_id_a}/replan",
        json={"reason": "Malicious replan attempt"},
        headers=headers_b,
    )
    assert cross_replan.status_code == 404
