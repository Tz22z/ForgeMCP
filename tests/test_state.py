import pytest

from forgemcp.core.models import TaskStatus
from forgemcp.core.state import InvalidTransition, TaskStateMachine


def test_happy_path_state_transitions() -> None:
    state = TaskStateMachine()
    for target in (
        TaskStatus.INDEXING,
        TaskStatus.PLANNING,
        TaskStatus.ACTING,
        TaskStatus.VERIFYING,
        TaskStatus.SUCCEEDED,
    ):
        state.transition(target)
    assert state.terminal


def test_terminal_state_cannot_transition() -> None:
    state = TaskStateMachine(status=TaskStatus.SUCCEEDED)
    with pytest.raises(InvalidTransition):
        state.transition(TaskStatus.PLANNING)
