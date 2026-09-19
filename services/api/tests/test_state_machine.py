"""Unit tests for the NEXUS Task State Machine."""

import pytest

from packages.shared.nexus_shared.errors import InvalidStateTransitionError
from packages.types.nexus_types.schemas import TaskStatus
from services.api.nexus_api.tasks.state_machine import (
    TERMINAL_STATES,
    is_terminal_state,
    validate_task_transition,
)


def test_terminal_states_detection():
    assert is_terminal_state(TaskStatus.COMPLETED) is True
    assert is_terminal_state(TaskStatus.FAILED) is True
    assert is_terminal_state(TaskStatus.CANCELLED) is True
    assert is_terminal_state(TaskStatus.EXECUTING) is False
    assert is_terminal_state(TaskStatus.PENDING) is False
    assert is_terminal_state("completed") is True
    assert is_terminal_state("unknown_state") is False


def test_valid_lifecycle_transitions():
    # PENDING -> PLANNING
    assert validate_task_transition(TaskStatus.PENDING, TaskStatus.PLANNING) == TaskStatus.PLANNING
    # PLANNING -> EXECUTING
    assert (
        validate_task_transition(TaskStatus.PLANNING, TaskStatus.EXECUTING) == TaskStatus.EXECUTING
    )
    # EXECUTING -> OBSERVING
    assert (
        validate_task_transition(TaskStatus.EXECUTING, TaskStatus.OBSERVING) == TaskStatus.OBSERVING
    )
    # OBSERVING -> EXECUTING
    assert (
        validate_task_transition(TaskStatus.OBSERVING, TaskStatus.EXECUTING) == TaskStatus.EXECUTING
    )
    # EXECUTING -> COMPLETED
    assert (
        validate_task_transition(TaskStatus.EXECUTING, TaskStatus.COMPLETED) == TaskStatus.COMPLETED
    )


def test_string_inputs_handled():
    assert validate_task_transition("pending", "executing") == TaskStatus.EXECUTING
    assert validate_task_transition("executing", "cancelled") == TaskStatus.CANCELLED


def test_transitions_from_terminal_states_rejected():
    for terminal in TERMINAL_STATES:
        for target in TaskStatus:
            with pytest.raises(
                InvalidStateTransitionError, match="Cannot transition from terminal state"
            ):
                validate_task_transition(terminal, target)


def test_invalid_arbitrary_transitions_rejected():
    # Cannot jump directly from PENDING to COMPLETED
    with pytest.raises(
        InvalidStateTransitionError, match="Invalid transition from 'pending' to 'completed'"
    ):
        validate_task_transition(TaskStatus.PENDING, TaskStatus.COMPLETED)

    # Cannot jump from AWAITING_APPROVAL to COMPLETED directly
    with pytest.raises(InvalidStateTransitionError):
        validate_task_transition(TaskStatus.AWAITING_APPROVAL, TaskStatus.COMPLETED)


def test_unknown_status_raises_error():
    with pytest.raises(InvalidStateTransitionError, match="Unknown current status"):
        validate_task_transition("invalid_status", TaskStatus.EXECUTING)

    with pytest.raises(InvalidStateTransitionError, match="Unknown target status"):
        validate_task_transition(TaskStatus.PENDING, "invalid_status")
