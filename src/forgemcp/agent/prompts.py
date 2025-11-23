"""Compact prompts that expose run state and selected repository evidence."""

from __future__ import annotations

from forgemcp.core.models import BudgetSpec, ContextBundle, Issue, Usage


def initial_prompt(issue: Issue, context: ContextBundle, budget: BudgetSpec) -> str:
    return f"""## Issue
{issue.prompt}

## Preselected repository context
{context.render() or "No relevant context was selected. Use search/list tools."}

## Hard run budgets
- tool calls: {budget.max_tool_calls}
- model calls: {budget.max_model_calls}
- input tokens: {budget.max_input_tokens}
- output tokens: {budget.max_output_tokens}
- wall time: {budget.max_wall_seconds}s

Begin by validating the likely fault, then edit and test. Keep an eye on the hard budgets.
"""


def continuation_prompt(usage: Usage, note: str = "") -> str:
    return f"""Continue from the tool results.
Usage so far: {usage.tool_calls} tool calls, {usage.model_calls} model calls,
{usage.input_tokens} input tokens, {usage.output_tokens} output tokens,
{usage.wall_seconds:.3f}s elapsed.
{note}
"""

