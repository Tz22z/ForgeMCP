"""Directional comparison of two aggregate evaluation reports."""

from __future__ import annotations

from typing import Any


def compare(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float | int | None]:
    baseline_cost = baseline.get("cost_per_solved_usd")
    candidate_cost = candidate.get("cost_per_solved_usd")
    cost_change = None
    if baseline_cost not in {None, 0} and candidate_cost is not None:
        cost_change = round(candidate_cost / baseline_cost - 1, 4)
    return {
        "attempted": int(candidate["attempted"]),
        "solve_rate_change": round(candidate["solve_rate"] - baseline["solve_rate"], 4),
        "average_tool_calls_change": round(
            candidate["average_tool_calls"] - baseline["average_tool_calls"], 3
        ),
        "repeated_read_ratio_change": round(
            candidate["average_repeated_read_ratio"] - baseline["average_repeated_read_ratio"],
            4,
        ),
        "cost_per_solved_relative_change": cost_change,
    }
