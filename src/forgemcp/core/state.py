"""Explicit task state machine used by the verified execution loop."""

from __future__ import annotations

from dataclasses import dataclass, field

from forgemcp.core.models import TaskStatus


class InvalidTransition(RuntimeError):
    pass


_ALLOWED: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.INDEXING, TaskStatus.BLOCKED},
    TaskStatus.INDEXING: {TaskStatus.PLANNING, TaskStatus.FAILED, TaskStatus.BUDGET_EXHAUSTED},
    TaskStatus.PLANNING: {
        TaskStatus.ACTING,
        TaskStatus.VERIFYING,
        TaskStatus.FAILED,
        TaskStatus.BUDGET_EXHAUSTED,
        TaskStatus.BLOCKED,
    },
    TaskStatus.ACTING: {
        TaskStatus.PLANNING,
        TaskStatus.VERIFYING,
        TaskStatus.FAILED,
        TaskStatus.BUDGET_EXHAUSTED,
        TaskStatus.BLOCKED,
    },
    TaskStatus.VERIFYING: {
        TaskStatus.PLANNING,
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.BUDGET_EXHAUSTED,
    },
    TaskStatus.SUCCEEDED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.BUDGET_EXHAUSTED: set(),
    TaskStatus.BLOCKED: set(),
}


@dataclass(slots=True)
class TaskStateMachine:
    status: TaskStatus = TaskStatus.CREATED
    history: list[TaskStatus] = field(default_factory=lambda: [TaskStatus.CREATED])

    def transition(self, target: TaskStatus) -> None:
        if target not in _ALLOWED[self.status]:
            raise InvalidTransition(f"cannot transition from {self.status} to {target}")
        self.status = target
        self.history.append(target)

    @property
    def terminal(self) -> bool:
        return not _ALLOWED[self.status]

