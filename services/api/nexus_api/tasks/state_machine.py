"""NEXUS Task Engine State Machine

Strict state transition validation for DAGs and subtask nodes.
Ensures deterministic progression and irreversible terminal state boundaries.
"""

from packages.shared.nexus_shared.errors import InvalidStateTransitionError
from packages.types.nexus_types.schemas import TaskStatus

TERMINAL_STATES: set[TaskStatus] = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}

VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {
        TaskStatus.PLANNING,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.EXECUTING,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.PLANNING: {
        TaskStatus.PENDING,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.EXECUTING,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.AWAITING_APPROVAL: {
        TaskStatus.PLANNING,
        TaskStatus.EXECUTING,
        TaskStatus.CANCELLED,
        TaskStatus.FAILED,
    },
    TaskStatus.EXECUTING: {
        TaskStatus.OBSERVING,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.OBSERVING: {
        TaskStatus.EXECUTING,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


def is_terminal_state(status: TaskStatus | str) -> bool:
    """Check if the given status is a terminal state."""
    if isinstance(status, str):
        try:
            status = TaskStatus(status)
        except ValueError:
            return False
    return status in TERMINAL_STATES


def validate_task_transition(current: TaskStatus | str, target: TaskStatus | str) -> TaskStatus:
    """Validate a transition between two states.

    Raises:
        InvalidStateTransitionError: If the transition is disallowed or from a terminal state.

    Returns:
        The validated target TaskStatus enum.
    """
    if isinstance(current, str):
        try:
            current_status = TaskStatus(current)
        except ValueError as err:
            raise InvalidStateTransitionError(f"Unknown current status: {current}") from err
    else:
        current_status = current

    if isinstance(target, str):
        try:
            target_status = TaskStatus(target)
        except ValueError as err:
            raise InvalidStateTransitionError(f"Unknown target status: {target}") from err
    else:
        target_status = target

    # Check terminal state restrictions
    if current_status in TERMINAL_STATES:
        raise InvalidStateTransitionError(
            f"Cannot transition from terminal state '{current_status.value}' to '{target_status.value}'"
        )

    # Check valid transition matrix
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        allowed_names = [s.value for s in allowed]
        raise InvalidStateTransitionError(
            f"Invalid transition from '{current_status.value}' to '{target_status.value}'. "
            f"Allowed transitions from '{current_status.value}': {allowed_names}"
        )

    return target_status
