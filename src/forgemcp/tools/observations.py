"""Bound tool output while retaining a durable reference to full content."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BoundedOutput:
    text: str
    truncated: bool
    reference: str | None


class ObservationStore:
    def __init__(self, directory: Path, max_chars: int = 12_000) -> None:
        self.directory = directory
        self.max_chars = max_chars

    def bound(self, call_id: str, content: str) -> BoundedOutput:
        if len(content) <= self.max_chars:
            return BoundedOutput(content, False, None)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{call_id}.txt"
        path.write_text(content, encoding="utf-8")
        head_size = int(self.max_chars * 0.7)
        tail_size = self.max_chars - head_size
        marker = (
            f"\n\n... output truncated; full observation: {path} "
            f"({len(content)} characters) ...\n\n"
        )
        text = content[:head_size] + marker + content[-tail_size:]
        return BoundedOutput(text, True, str(path))
