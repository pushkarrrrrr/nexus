"""NEXUS Task Orchestration & Management Routes

Provides endpoints for creating, executing, stepping, cancelling,
and tracking the lifecycle and timeline of task DAGs.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.shared.nexus_shared.errors import InvalidStateTransitionError
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import (
    DAGNodeModel,
    SessionModel,
    TaskDAGModel,
    TaskEventModel,
    UserModel,
    generate_uuid,
)
from packages.types.nexus_types.schemas import (
    DAGNode,
    DAGNodeCreateRequest,
    DAGNodeTransitionRequest,
    TaskCancelRequest,
    TaskCreateRequest,
    TaskDAG,
    TaskEventResponse,
    TaskStatus,
    TaskTimelineResponse,
    TaskTransitionRequest,
)
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.database import get_db
from services.api.nexus_api.tasks.state_machine import (
    is_terminal_state,
    validate_task_transition,
)
from services.api.nexus_api.websocket import broadcast_event

logger = get_logger("nexus.tasks")
tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])


def _format_dag_node(model: DAGNodeModel) -> DAGNode:
    """Format DAGNodeModel to DAGNode response schema."""
    return DAGNode(
        id=str(model.id),
        name=str(model.name),
        agent=str(model.agent_name),
        tool=str(model.tool_name) if model.tool_name else None,
        input=dict(model.input_payload) if model.input_payload else None,
        dependencies=list(model.dependencies or []),
        status=TaskStatus(model.status),
        result=dict(model.result_payload) if model.result_payload else None,
        error=str(model.error_message) if model.error_message else None,
        started_at=model.started_at,
        completed_at=model.completed_at,
    )


def _format_task_dag(model: TaskDAGModel) -> TaskDAG:
    """Format TaskDAGModel to TaskDAG response schema."""
    nodes = [_format_dag_node(n) for n in (model.nodes or [])]
    return TaskDAG(
        dag_id=str(model.id),
        session_id=str(model.session_id),
        goal=str(model.goal),
        nodes=nodes,
        status=TaskStatus(model.status),
        user_id=str(model.user_id) if model.user_id else None,
        execution_metadata=dict(model.execution_metadata or {}),
        created_at=model.created_at,
        completed_at=model.completed_at,
    )


@tasks_router.post("", response_model=TaskDAG, status_code=status.HTTP_201_CREATED)
async def create_task(
    req: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> TaskDAG:
    """Create a new Task DAG and its initial subtasks/nodes."""
    # Resolve or create session
    session_id = req.session_id
    if session_id:
        sess_query = await db.execute(
            select(SessionModel).where(
                SessionModel.id == session_id,
                SessionModel.user_id == current_user.id,
            )
        )
        if not sess_query.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found for user",
            )
    else:
        # Check for user's latest session or create a default one
        latest_sess_q = await db.execute(
            select(SessionModel)
            .where(SessionModel.user_id == current_user.id)
            .order_by(desc(SessionModel.created_at))
            .limit(1)
        )
        latest_sess = latest_sess_q.scalar_one_or_none()
        if latest_sess:
            session_id = str(latest_sess.id)
        else:
            new_sess = SessionModel(
                user_id=current_user.id,
                surface="dashboard",
                title=f"Session - {req.goal[:32]}",
            )
            db.add(new_sess)
            await db.flush()
            session_id = str(new_sess.id)

    dag_id = generate_uuid("dag")
    dag = TaskDAGModel(
        id=dag_id,
        user_id=current_user.id,
        session_id=session_id,
        goal=req.goal,
        status=TaskStatus.PENDING.value,
        execution_metadata=req.execution_metadata,
        created_at=datetime.now(UTC),
    )
    db.add(dag)
    await db.flush()

    created_nodes: list[DAGNodeModel] = []
    for node_req in req.nodes:
        node_id = node_req.id or generate_uuid("step")
        node_model = DAGNodeModel(
            id=node_id,
            dag_id=dag.id,
            name=node_req.name,
            agent_name=node_req.agent,
            tool_name=node_req.tool,
            input_payload=node_req.input,
            dependencies=node_req.dependencies,
            status=TaskStatus.PENDING.value,
        )
        db.add(node_model)
        created_nodes.append(node_model)

    # Record initial DAG created timeline event
    initial_event = TaskEventModel(
        dag_id=dag.id,
        event_type="dag_created",
        from_state=None,
        to_state=TaskStatus.PENDING.value,
        message=f"Task created with goal: {req.goal}",
        payload={"node_count": len(created_nodes)},
        created_at=datetime.now(UTC),
    )
    db.add(initial_event)
    await db.commit()

    # Re-query with eager nodes loading
    refreshed_q = await db.execute(
        select(TaskDAGModel)
        .where(TaskDAGModel.id == dag.id)
        .options(selectinload(TaskDAGModel.nodes))
    )
    refreshed_dag = refreshed_q.scalar_one()

    # Real-time WebSocket broadcast
    await broadcast_event(
        "dag.updated",
        session_id=session_id,
        payload={
            "task_id": dag.id,
            "goal": dag.goal,
            "status": dag.status,
            "node_count": len(created_nodes),
        },
    )

    logger.info("task_dag_created", task_id=dag.id, user_id=current_user.id, goal=req.goal)
    return _format_task_dag(refreshed_dag)


@tasks_router.get("", response_model=list[TaskDAG])
async def list_tasks(
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> list[TaskDAG]:
    """List all task DAGs for the authenticated user, optionally filtered by status."""
    stmt = (
        select(TaskDAGModel)
        .where(TaskDAGModel.user_id == current_user.id)
        .options(selectinload(TaskDAGModel.nodes))
        .order_by(desc(TaskDAGModel.created_at))
    )
    if status_filter:
        stmt = stmt.where(TaskDAGModel.status == status_filter.value)

    res = await db.execute(stmt)
    dags = res.scalars().all()
    return [_format_task_dag(d) for d in dags]


@tasks_router.get("/{task_id}", response_model=TaskDAG)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> TaskDAG:
    """Get full details of a specific task DAG including its subtask nodes."""
    res = await db.execute(
        select(TaskDAGModel)
        .where(TaskDAGModel.id == task_id, TaskDAGModel.user_id == current_user.id)
        .options(selectinload(TaskDAGModel.nodes))
    )
    dag = res.scalar_one_or_none()
    if not dag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )
    return _format_task_dag(dag)


@tasks_router.post("/{task_id}/steps", response_model=DAGNode, status_code=status.HTTP_201_CREATED)
async def add_task_step(
    task_id: str,
    req: DAGNodeCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> DAGNode:
    """Add a new subtask node/step to an existing non-terminal task DAG."""
    res = await db.execute(
        select(TaskDAGModel).where(
            TaskDAGModel.id == task_id, TaskDAGModel.user_id == current_user.id
        )
    )
    dag = res.scalar_one_or_none()
    if not dag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )

    if is_terminal_state(dag.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add steps to task in terminal state '{dag.status}'",
        )

    node_id = req.id or generate_uuid("step")
    node_model = DAGNodeModel(
        id=node_id,
        dag_id=dag.id,
        name=req.name,
        agent_name=req.agent,
        tool_name=req.tool,
        input_payload=req.input,
        dependencies=req.dependencies,
        status=TaskStatus.PENDING.value,
    )
    db.add(node_model)

    event = TaskEventModel(
        dag_id=dag.id,
        node_id=node_id,
        event_type="node_created",
        from_state=None,
        to_state=TaskStatus.PENDING.value,
        message=f"Added subtask step: {req.name}",
        payload={"step_name": req.name, "agent": req.agent},
        created_at=datetime.now(UTC),
    )
    db.add(event)
    await db.commit()
    await db.refresh(node_model)

    await broadcast_event(
        "dag.updated",
        session_id=str(dag.session_id),
        payload={"task_id": dag.id, "step_id": node_id, "action": "step_added"},
    )

    return _format_dag_node(node_model)


@tasks_router.post("/{task_id}/transition", response_model=TaskDAG)
async def transition_task(
    task_id: str,
    req: TaskTransitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> TaskDAG:
    """Transition a task DAG state with deterministic state machine validation."""
    res = await db.execute(
        select(TaskDAGModel)
        .where(TaskDAGModel.id == task_id, TaskDAGModel.user_id == current_user.id)
        .options(selectinload(TaskDAGModel.nodes))
    )
    dag = res.scalar_one_or_none()
    if not dag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )

    old_status = str(dag.status)
    try:
        new_status = validate_task_transition(old_status, req.to_state)
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err

    dag.status = new_status.value
    if is_terminal_state(new_status):
        dag.completed_at = datetime.now(UTC)

    if req.execution_metadata:
        current_meta = dict(dag.execution_metadata or {})
        current_meta.update(req.execution_metadata)
        dag.execution_metadata = current_meta

    # Determine event type
    event_type = "state_transition"
    if new_status == TaskStatus.COMPLETED:
        event_type = "task_completed"
    elif new_status == TaskStatus.FAILED:
        event_type = "task_failed"
    elif new_status == TaskStatus.CANCELLED:
        event_type = "task_cancelled"

    event = TaskEventModel(
        dag_id=dag.id,
        event_type=event_type,
        from_state=old_status,
        to_state=new_status.value,
        message=req.reason or f"Task transitioned from {old_status} to {new_status.value}",
        payload=req.execution_metadata or {},
        created_at=datetime.now(UTC),
    )
    db.add(event)
    await db.commit()
    await db.refresh(dag)

    await broadcast_event(
        "task.state_changed",
        session_id=str(dag.session_id),
        payload={
            "task_id": dag.id,
            "from_state": old_status,
            "to_state": new_status.value,
            "reason": req.reason,
        },
    )

    logger.info(
        "task_transitioned",
        task_id=dag.id,
        from_state=old_status,
        to_state=new_status.value,
    )
    return _format_task_dag(dag)


@tasks_router.post("/{task_id}/steps/{step_id}/transition", response_model=DAGNode)
async def transition_task_step(
    task_id: str,
    step_id: str,
    req: DAGNodeTransitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> DAGNode:
    """Transition a subtask step status with state machine validation."""
    dag_q = await db.execute(
        select(TaskDAGModel).where(
            TaskDAGModel.id == task_id, TaskDAGModel.user_id == current_user.id
        )
    )
    dag = dag_q.scalar_one_or_none()
    if not dag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )

    node_q = await db.execute(
        select(DAGNodeModel).where(DAGNodeModel.id == step_id, DAGNodeModel.dag_id == task_id)
    )
    node = node_q.scalar_one_or_none()
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Step '{step_id}' not found in task '{task_id}'",
        )

    old_status = str(node.status)
    try:
        new_status = validate_task_transition(old_status, req.to_state)
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err

    node.status = new_status.value
    now = datetime.now(UTC)
    if new_status == TaskStatus.EXECUTING and not node.started_at:
        node.started_at = now
    elif is_terminal_state(new_status):
        node.completed_at = now

    if req.result is not None:
        node.result_payload = req.result
    if req.error is not None:
        node.error_message = req.error

    event = TaskEventModel(
        dag_id=dag.id,
        node_id=node.id,
        event_type="node_state_transition",
        from_state=old_status,
        to_state=new_status.value,
        message=f"Step '{node.name}' transitioned from {old_status} to {new_status.value}",
        payload={"result": req.result, "error": req.error},
        created_at=now,
    )
    db.add(event)
    await db.commit()
    await db.refresh(node)

    await broadcast_event(
        "step.state_changed",
        session_id=str(dag.session_id),
        payload={
            "task_id": dag.id,
            "step_id": node.id,
            "from_state": old_status,
            "to_state": new_status.value,
        },
    )

    logger.info(
        "step_transitioned",
        task_id=dag.id,
        step_id=node.id,
        from_state=old_status,
        to_state=new_status.value,
    )
    return _format_dag_node(node)


@tasks_router.post("/{task_id}/cancel", response_model=TaskDAG)
async def cancel_task(
    task_id: str,
    req: TaskCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> TaskDAG:
    """Perform cascading cancellation on a task DAG and all non-terminal subtasks."""
    res = await db.execute(
        select(TaskDAGModel)
        .where(TaskDAGModel.id == task_id, TaskDAGModel.user_id == current_user.id)
        .options(selectinload(TaskDAGModel.nodes))
    )
    dag = res.scalar_one_or_none()
    if not dag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )

    old_status = str(dag.status)
    if is_terminal_state(old_status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel task already in terminal state '{old_status}'",
        )

    now = datetime.now(UTC)
    dag.status = TaskStatus.CANCELLED.value
    dag.completed_at = now

    cancelled_nodes_count = 0
    for node in dag.nodes:
        if not is_terminal_state(node.status):
            node.status = TaskStatus.CANCELLED.value
            node.completed_at = now
            cancelled_nodes_count += 1

    event = TaskEventModel(
        dag_id=dag.id,
        event_type="task_cancelled",
        from_state=old_status,
        to_state=TaskStatus.CANCELLED.value,
        message=f"Task cancelled: {req.reason}",
        payload={"reason": req.reason, "cancelled_nodes": cancelled_nodes_count},
        created_at=now,
    )
    db.add(event)
    await db.commit()
    await db.refresh(dag)

    await broadcast_event(
        "task.cancelled",
        session_id=str(dag.session_id),
        payload={
            "task_id": dag.id,
            "reason": req.reason,
            "cancelled_nodes": cancelled_nodes_count,
        },
    )

    logger.info(
        "task_cancelled",
        task_id=dag.id,
        reason=req.reason,
        cancelled_nodes=cancelled_nodes_count,
    )
    return _format_task_dag(dag)


@tasks_router.get("/{task_id}/timeline", response_model=TaskTimelineResponse)
async def get_task_timeline(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> TaskTimelineResponse:
    """Retrieve chronological event history and audit timeline for a task DAG."""
    dag_q = await db.execute(
        select(TaskDAGModel).where(
            TaskDAGModel.id == task_id, TaskDAGModel.user_id == current_user.id
        )
    )
    if not dag_q.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )

    events_q = await db.execute(
        select(TaskEventModel)
        .where(TaskEventModel.dag_id == task_id)
        .order_by(TaskEventModel.created_at.asc())
    )
    events = events_q.scalars().all()

    formatted_events = [
        TaskEventResponse(
            id=str(e.id),
            dag_id=str(e.dag_id),
            node_id=str(e.node_id) if e.node_id else None,
            event_type=str(e.event_type),
            from_state=str(e.from_state) if e.from_state else None,
            to_state=str(e.to_state) if e.to_state else None,
            message=str(e.message),
            payload=dict(e.payload or {}),
            created_at=e.created_at,
        )
        for e in events
    ]

    return TaskTimelineResponse(
        dag_id=task_id,
        events=formatted_events,
        total_events=len(formatted_events),
    )
