from pathlib import Path

import pytest
from pydantic import ValidationError

from forgemcp.config import load_config
from forgemcp.core.models import BudgetSpec, ContextSnippet, Issue


def test_issue_prompt_includes_acceptance_criteria() -> None:
    issue = Issue(title="Fix cache", body="Cache goes stale.", acceptance_criteria=["Tests pass"])
    assert "Fix cache" in issue.prompt
    assert "- Tests pass" in issue.prompt


def test_budget_rejects_zero_calls() -> None:
    with pytest.raises(ValidationError):
        BudgetSpec(max_tool_calls=0)


def test_context_snippet_rejects_reversed_range() -> None:
    with pytest.raises(ValidationError):
        ContextSnippet(
            path="a.py",
            start_line=10,
            end_line=2,
            text="pass",
            score=1.0,
            estimated_tokens=1,
        )


def test_load_config_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert config.repository == tmp_path.resolve()
    assert config.budget.max_tool_calls == 30
