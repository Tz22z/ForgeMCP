"""Central accounting for time, token, call, and repetition budgets."""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from forgemcp.core.models import BudgetSpec, Usage


class BudgetExceeded(RuntimeError):
    """Raised before an action that would cross a hard run limit."""

    def __init__(self, dimension: str, used: int | float, limit: int | float) -> None:
        self.dimension = dimension
        self.used = used
        self.limit = limit
        super().__init__(f"{dimension} budget exhausted ({used}/{limit})")


@dataclass(slots=True)
class BudgetLedger:
    spec: BudgetSpec
    started: float = field(default_factory=lambda: time.monotonic())
    _tool_calls: int = 0
    _model_calls: int = 0
    _input_tokens: int = 0
    _output_tokens: int = 0
    _fingerprints: Counter[str] = field(default_factory=Counter)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    @property
    def usage(self) -> Usage:
        return Usage(
            tool_calls=self._tool_calls,
            model_calls=self._model_calls,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            wall_seconds=round(self.elapsed, 3),
        )

    def check_time(self) -> None:
        elapsed = self.elapsed
        if elapsed >= self.spec.max_wall_seconds:
            raise BudgetExceeded("wall_seconds", round(elapsed, 3), self.spec.max_wall_seconds)

    def reserve_tool_call(self, name: str, arguments: dict[str, Any]) -> str:
        self.check_time()
        if self._tool_calls >= self.spec.max_tool_calls:
            raise BudgetExceeded("tool_calls", self._tool_calls, self.spec.max_tool_calls)

        fingerprint = self.fingerprint(name, arguments)
        repeats = self._fingerprints[fingerprint]
        if repeats > self.spec.max_repeated_actions:
            raise BudgetExceeded(
                "repeated_actions",
                repeats,
                self.spec.max_repeated_actions,
            )
        self._fingerprints[fingerprint] += 1
        self._tool_calls += 1
        return fingerprint

    def reserve_model_call(self) -> None:
        self.check_time()
        if self._model_calls >= self.spec.max_model_calls:
            raise BudgetExceeded("model_calls", self._model_calls, self.spec.max_model_calls)
        self._model_calls += 1

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        next_input = self._input_tokens + max(0, input_tokens)
        next_output = self._output_tokens + max(0, output_tokens)
        if next_input > self.spec.max_input_tokens:
            raise BudgetExceeded("input_tokens", next_input, self.spec.max_input_tokens)
        if next_output > self.spec.max_output_tokens:
            raise BudgetExceeded("output_tokens", next_output, self.spec.max_output_tokens)
        self._input_tokens = next_input
        self._output_tokens = next_output

    @staticmethod
    def fingerprint(name: str, arguments: dict[str, Any]) -> str:
        canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(f"{name}:{canonical}".encode()).hexdigest()[:16]
