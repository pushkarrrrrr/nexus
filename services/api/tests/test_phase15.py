"""Comprehensive tests for Phase 15 Autonomous Self-Correction, Dynamic Replanning & Error Recovery."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from packages.shared.nexus_shared.agents.recovery import (
    DAGPatcher,
    ErrorClassifier,
    ProposedRecoveryStep,
    SelfCorrectionCoordinator,
    SelfCorrectionProposal,
    SelfCorrectionReflector,
)
from packages.shared.nexus_shared.models import (
    ActionSnapshotModel,
    ApprovalRequestModel,
    ExecutionPlanModel,
    PlanStepModel,
    SessionModel,
    TaskDAGModel,
    UserModel,
    generate_uuid,
    utcnow,
)
from packages.shared.nexus_shared.reversal import SnapshotManager
from services.api.nexus_api.database import get_session_factory, init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


async def create_test_user():
    """Helper to create an authenticated user in test DB and return headers & UserModel."""
    await init_database()
    factory = get_session_factory()
    user_id = f"usr_{uuid.uuid4().hex[:16]}"
    async with factory() as session:
        user = UserModel(
            id=user_id,
            email=f"test_phase15_{uuid.uuid4().hex[:8]}@nexus.local",
            hashed_password="argon2id$mockhash",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    from services.api.nexus_api.auth.security import create_access_token

    token = create_access_token(user_id=user.id, email=user.email)
    headers = {"Authorization": f"Bearer {token}"}
    return headers, user


# ============================================================================
# 1. Error Classifier Unit Tests
# ============================================================================
def test_error_classifier_all_categories():
    assert ErrorClassifier.classify("ValidationError: 1 validation error for ToolInput") == "PARAM_INVALID"
    assert ErrorClassifier.classify("TypeError: execute() missing 1 required positional argument: 'params'") == "PARAM_INVALID"
    assert ErrorClassifier.classify("Action denied: blocked by policy engine") == "POLICY_REJECTED"
    assert ErrorClassifier.classify("Permission denied for execution") == "POLICY_REJECTED"
    assert ErrorClassifier.classify("Operation timed out after 30 seconds") == "TIMEOUT"
    assert ErrorClassifier.classify("Deadline exceeded while waiting for host response") == "TIMEOUT"
    assert ErrorClassifier.classify("FileNotFoundError: [Errno 2] No such file or directory: 'config.json'") == "RESOURCE_NOT_FOUND"
    assert ErrorClassifier.classify("HTTP 404: resource not found on remote server") == "RESOURCE_NOT_FOUND"
    assert ErrorClassifier.classify("Connection refused: 127.0.0.1:9092") == "ENVIRONMENT_ERROR"
    assert ErrorClassifier.classify("OSError: Read-only file system") == "ENVIRONMENT_ERROR"
    assert ErrorClassifier.classify("RuntimeError: Subprocess exited with code 1") == "TOOL_FAILURE"
    assert ErrorClassifier.classify("") == "UNKNOWN"


# ============================================================================
# 2. Reflector & Proposal Generation Tests
# ============================================================================
def test_reflector_heuristic_fallback():
    reflector = SelfCorrectionReflector()
    step = PlanStepModel(
        id="pstep_test_1",
        plan_id="plan_test_1",
        index=1,
        description="Write output to /tmp/results.csv",
        assigned_agent="orchestrator",
        required_tools=["filesystem.write"],
    )

    # Heuristic fallback for RESOURCE_NOT_FOUND
    prop_not_found = reflector._heuristic_fallback(
        goal="Extract data and write to file",
        failed_step=step,
        error_context="No such file or directory: /tmp/results.csv",
        error_category="RESOURCE_NOT_FOUND",
        has_snapshot=False,
    )
    assert prop_not_found.strategy == "PRUNE_AND_SPLICE_DAG"
    assert len(prop_not_found.recovery_steps) == 2
    assert "Discover" in prop_not_found.recovery_steps[0].description

    # Heuristic fallback for dirty state with snapshot
    prop_rollback = reflector._heuristic_fallback(
        goal="Update configuration file",
        failed_step=step,
        error_context="OSError: write failed midway",
        error_category="ENVIRONMENT_ERROR",
        has_snapshot=True,
    )
    assert prop_rollback.strategy == "ROLLBACK_AND_RETRY"
    assert prop_rollback.requires_rollback is True

    # Heuristic fallback for POLICY_REJECTED
    prop_policy = reflector._heuristic_fallback(
        goal="Delete system files",
        failed_step=step,
        error_context="Action rejected by policy engine",
        error_category="POLICY_REJECTED",
        has_snapshot=False,
    )
    assert prop_policy.strategy == "ESCALATE_HITL"
    assert prop_policy.requires_hitl is True


@pytest.mark.asyncio
async def test_reflector_structured_llm_completion():
    reflector = SelfCorrectionReflector()
    step = PlanStepModel(
        id="pstep_test_2",
        plan_id="plan_test_2",
        index=0,
        description="Search arXiv for papers",
        assigned_agent="research",
        required_tools=["arxiv.search"],
    )

    mock_proposal = SelfCorrectionProposal(
        error_category="TOOL_FAILURE",
        diagnosis="arXiv API returned rate limit 429. Substitute with EuropePMC tool.",
        strategy="FALLBACK_TOOL",
        requires_rollback=False,
        requires_hitl=False,
        recovery_steps=[
            ProposedRecoveryStep(
                description="Query EuropePMC for papers instead of arXiv",
                assigned_agent="research",
                required_tools=["europepmc.search"],
                dependencies=[],
            )
        ],
    )

    with patch.object(reflector.gateway, "complete_structured", new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = (mock_proposal, None)
        proposal = await reflector.reflect(
            goal="Find relevant multi-agent papers",
            failed_step=step,
            error_context="HTTP 429 Too Many Requests",
            error_category="TOOL_FAILURE",
        )
        assert proposal.strategy == "FALLBACK_TOOL"
        assert "EuropePMC" in proposal.diagnosis
        assert len(proposal.recovery_steps) == 1
        assert proposal.recovery_steps[0].required_tools == ["europepmc.search"]


# ============================================================================
# 3. DAG Patcher Splicing and Dependency Rewiring Tests
# ============================================================================
@pytest.mark.asyncio
async def test_dag_patcher_splicing_and_deps():
    factory = get_session_factory()
    _, user = await create_test_user()

    async with factory() as session:
        # 1. Create Session, Task & Plan with 3 sequential steps
        sess = SessionModel(
            id=generate_uuid("sess"),
            user_id=user.id,
            surface="dashboard",
        )
        task = TaskDAGModel(
            id=generate_uuid("task"),
            user_id=user.id,
            session_id=sess.id,
            goal="Multi-step data pipeline",
            status="executing",
        )
        plan = ExecutionPlanModel(
            id=generate_uuid("plan"),
            task_id=task.id,
            user_id=user.id,
            goal="Multi-step data pipeline",
            status="executing",
            replan_count=0,
        )
        session.add_all([sess, task, plan])
        await session.flush()

        id_a = generate_uuid("pstep")
        id_b = generate_uuid("pstep")
        id_c = generate_uuid("pstep")

        step_a = PlanStepModel(
            id=id_a,
            plan_id=plan.id,
            index=0,
            description="Fetch dataset",
            assigned_agent="research",
            status="completed",
            dependencies=[],
        )
        step_b = PlanStepModel(
            id=id_b,
            plan_id=plan.id,
            index=1,
            description="Process dataset (FAILS)",
            assigned_agent="orchestrator",
            status="failed",
            dependencies=[id_a],
        )
        step_c = PlanStepModel(
            id=id_c,
            plan_id=plan.id,
            index=2,
            description="Generate final report",
            assigned_agent="document",
            status="pending",
            dependencies=[id_b],
        )
        session.add_all([step_a, step_b, step_c])
        await session.commit()

        # 2. Patch plan with 2 recovery steps replacing step_b
        proposal = SelfCorrectionProposal(
            error_category="TOOL_FAILURE",
            diagnosis="Processing failed due to memory limit. Chunk processing into 2 smaller batches.",
            strategy="PRUNE_AND_SPLICE_DAG",
            requires_rollback=False,
            requires_hitl=False,
            recovery_steps=[
                ProposedRecoveryStep(
                    description="Process Batch 1",
                    assigned_agent="orchestrator",
                    required_tools=["processor"],
                    dependencies=[id_a],
                ),
                ProposedRecoveryStep(
                    description="Process Batch 2",
                    assigned_agent="orchestrator",
                    required_tools=["processor"],
                    dependencies=[],
                ),
            ],
        )

        recovery_steps = await DAGPatcher.patch_plan(
            session=session,
            plan=plan,
            failed_step=step_b,
            proposal=proposal,
        )

        assert len(recovery_steps) == 2
        assert step_b.status == "superseded"
        assert recovery_steps[0].index == 2
        assert recovery_steps[1].index == 3
        assert recovery_steps[0].is_recovery_step is True
        assert recovery_steps[0].replaces_step_id == step_b.id

        # Verify step_c index shifted from 2 to 4
        assert step_c.index == 4
        # Verify step_c's dependency re-wired from step_b to last recovery step
        assert step_c.dependencies == [recovery_steps[1].id]
        assert plan.replan_count == 1


# ============================================================================
# 4. Self-Correction Coordinator & Rollback Tests
# ============================================================================
@pytest.mark.asyncio
async def test_coordinator_handles_file_rollback():
    factory = get_session_factory()
    _, user = await create_test_user()

    async with factory() as session:
        sess = SessionModel(
            id=generate_uuid("sess"),
            user_id=user.id,
            surface="dashboard",
        )
        task = TaskDAGModel(
            id=generate_uuid("task"),
            user_id=user.id,
            session_id=sess.id,
            goal="File modification task",
            status="executing",
        )
        plan = ExecutionPlanModel(
            id=generate_uuid("plan"),
            task_id=task.id,
            user_id=user.id,
            goal="File modification task",
            status="executing",
            replan_count=0,
        )
        session.add_all([sess, task, plan])
        await session.flush()

        # Create an ActionSnapshotModel in DB
        snapshot = ActionSnapshotModel(
            user_id=user.id,
            task_id=task.id,
            capability_name="filesystem.write",
            action_type="FILE_MODIFY",
            is_reversible=True,
            target_path="/tmp/test_phase15.txt",
            before_state={"content": "original content"},
            after_state={"content": "corrupted content"},
            diff_patch="--- a\n+++ b\n",
            status="APPLIED",
            created_at=utcnow(),
        )
        session.add(snapshot)
        await session.flush()

        failed_step = PlanStepModel(
            id=generate_uuid("pstep"),
            plan_id=plan.id,
            index=0,
            description="Mutate file",
            assigned_agent="orchestrator",
            status="failed",
            result_payload={"snapshot_id": snapshot.id},
        )
        session.add(failed_step)
        await session.commit()

        coordinator = SelfCorrectionCoordinator()

        with patch.object(SnapshotManager, "revert_action", new_callable=AsyncMock) as mock_revert:
            mock_revert.return_value = snapshot

            created_steps, record, _proposal = await coordinator.handle_step_failure(
                session=session,
                plan=plan,
                failed_step=failed_step,
                error_context="OSError: Write failure after partial overwrite",
            )

            assert len(created_steps) >= 1
            assert record.snapshot_id == snapshot.id
            assert record.rollback_performed is True
            mock_revert.assert_awaited_once()


@pytest.mark.asyncio
async def test_coordinator_replan_budget_exhaustion_hitl():
    factory = get_session_factory()
    _, user = await create_test_user()

    async with factory() as session:
        sess = SessionModel(
            id=generate_uuid("sess"),
            user_id=user.id,
            surface="dashboard",
        )
        task = TaskDAGModel(
            id=generate_uuid("task"),
            user_id=user.id,
            session_id=sess.id,
            goal="Difficult task",
            status="executing",
        )
        plan = ExecutionPlanModel(
            id=generate_uuid("plan"),
            task_id=task.id,
            user_id=user.id,
            goal="Difficult task",
            status="executing",
            replan_count=3,
            max_replans=3,  # Budget exhausted!
        )
        session.add_all([sess, task, plan])
        await session.flush()

        failed_step = PlanStepModel(
            id=generate_uuid("pstep"),
            plan_id=plan.id,
            index=0,
            description="Repeatedly failing step",
            assigned_agent="orchestrator",
            status="failed",
        )
        session.add(failed_step)
        await session.commit()

        coordinator = SelfCorrectionCoordinator()
        _created_steps, record, _proposal = await coordinator.handle_step_failure(
            session=session,
            plan=plan,
            failed_step=failed_step,
            error_context="Recurring RuntimeError: unreachable host",
        )

        assert record.status == "escalated_hitl"

        # Verify ApprovalRequestModel was created in DB
        stmt_appr = select(ApprovalRequestModel).where(
            ApprovalRequestModel.user_id == user.id,
            ApprovalRequestModel.capability_name == "orchestrator.replan_recovery",
        )
        res = await session.execute(stmt_appr)
        approval = res.scalar_one_or_none()
        assert approval is not None
        assert approval.risk_level == "HIGH"
        assert "Self-correction requires approval" in approval.reason


# ============================================================================
# 5. REST API & System Status Verification Tests
# ============================================================================
@pytest.mark.asyncio
async def test_api_plan_reflections_and_diagnose():
    headers, user = await create_test_user()
    transport = ASGITransport(app=app)
    factory = get_session_factory()

    async with factory() as session:
        sess = SessionModel(
            id=generate_uuid("sess"),
            user_id=user.id,
            surface="dashboard",
        )
        task = TaskDAGModel(
            id=generate_uuid("task"),
            user_id=user.id,
            session_id=sess.id,
            goal="API test plan",
            status="executing",
        )
        plan = ExecutionPlanModel(
            id=generate_uuid("plan"),
            task_id=task.id,
            user_id=user.id,
            goal="API test plan",
            status="executing",
            replan_count=0,
        )
        session.add_all([sess, task, plan])
        await session.flush()

        step = PlanStepModel(
            id=generate_uuid("pstep"),
            plan_id=plan.id,
            index=0,
            description="API step",
            assigned_agent="orchestrator",
            status="failed",
            error_message="Simulated API failure",
        )
        session.add(step)
        await session.commit()

        plan_id = plan.id
        step_id = step.id

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Trigger diagnose endpoint
        diagnose_res = await client.post(
            f"/api/v1/plans/{plan_id}/reflections/diagnose",
            headers=headers,
            json={"step_id": step_id, "error_override": "Custom diagnosed error"},
        )
        assert diagnose_res.status_code == 200
        diag_data = diagnose_res.json()
        assert diag_data["plan_id"] == plan_id
        assert diag_data["step_id"] == step_id
        assert "strategy" in diag_data
        assert "diagnosis" in diag_data

        # 2. Query reflections endpoint
        list_res = await client.get(
            f"/api/v1/plans/{plan_id}/reflections",
            headers=headers,
        )
        assert list_res.status_code == 200
        records = list_res.json()
        assert len(records) >= 1
        assert records[0]["id"] == diag_data["id"]


@pytest.mark.asyncio
async def test_system_status_phase15():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/system/status")
        assert res.status_code == 200
        data = res.json()
        assert data["phase"] in (
            "phase_15_self_correction_recovery",
            "phase_16_academic_benchmarking_evaluation",
        )
        assert "dashboard" in data["supported_surfaces"]
        assert "ambient" in data["supported_surfaces"]
