from typing import Any


class SnapshotHistory:
    def __init__(self, initial: dict[str, Any]) -> None:
        self.state = initial
        self._snapshots: list[dict[str, Any]] = []

    def save(self) -> None:
        self._snapshots.append(self.state.copy())

    def restore(self) -> dict[str, Any]:
        if not self._snapshots:
            raise LookupError("no saved snapshot")
        self.state = self._snapshots.pop()
        return self.state
