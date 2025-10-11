"""Append-only JSONL event journal for replay, debugging, and evaluation."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from forgemcp.core.models import utc_now

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|authorization|token)([\"'=:\s]+)([^\s\"']+)"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
]


def redact(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.startswith("sk-"):
            redacted = pattern.sub("[REDACTED]", redacted)
        else:
            redacted = pattern.sub(r"\1\2[REDACTED]", redacted)
    return redacted


@dataclass(frozen=True, slots=True)
class Event:
    run_id: str
    kind: str
    payload: dict[str, Any]
    timestamp: datetime
    sequence: int


class EventJournal:
    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self._sequence = 0
        path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, kind: str, payload: dict[str, Any] | None = None) -> Event:
        self._sequence += 1
        safe_payload = self._sanitize(payload or {})
        event = Event(
            run_id=self.run_id,
            kind=kind,
            payload=safe_payload,
            timestamp=utc_now(),
            sequence=self._sequence,
        )
        record = asdict(event)
        record["timestamp"] = event.timestamp.isoformat()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        return event

    def read_all(self) -> list[Event]:
        if not self.path.exists():
            return []
        events: list[Event] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            raw = json.loads(line)
            raw["timestamp"] = datetime.fromisoformat(raw["timestamp"])
            events.append(Event(**raw))
        return events

    @classmethod
    def _sanitize(cls, value: Any) -> Any:
        if isinstance(value, str):
            return redact(value)
        if isinstance(value, dict):
            return {str(key): cls._sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._sanitize(item) for item in value]
        if isinstance(value, tuple):
            return [cls._sanitize(item) for item in value]
        return value

