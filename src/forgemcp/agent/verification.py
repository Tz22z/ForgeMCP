"""Normalize test command observations into completion evidence."""

from __future__ import annotations

import re

from forgemcp.core.models import TestReport
from forgemcp.tools.toolset import RawObservation

_COUNT = re.compile(r"(?P<count>\d+) (?P<kind>passed|failed|error|errors|skipped)")


def parse_test_observation(observation: RawObservation) -> TestReport:
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for match in _COUNT.finditer(observation.output):
        kind = match.group("kind")
        normalized = "errors" if kind in {"error", "errors"} else kind
        counts[normalized] = int(match.group("count"))
    lines = [line for line in observation.output.splitlines() if line.strip()]
    return TestReport(
        command=list(observation.metadata.get("command", [])),
        exit_code=int(observation.metadata.get("exit_code", 1)),
        passed=counts["passed"],
        failed=counts["failed"],
        errors=counts["errors"],
        skipped=counts["skipped"],
        duration_seconds=float(observation.metadata.get("elapsed_seconds", 0.0)),
        summary=lines[-1][:1_000] if lines else "",
    )

