from unittest.mock import patch

import pytest

from forgemcp.core.budget import BudgetExceeded, BudgetLedger
from forgemcp.core.models import BudgetSpec


def test_tool_call_budget_is_hard_limit() -> None:
    ledger = BudgetLedger(BudgetSpec(max_tool_calls=1))
    ledger.reserve_tool_call("read_file", {"path": "a.py"})
    with pytest.raises(BudgetExceeded, match="tool_calls"):
        ledger.reserve_tool_call("read_file", {"path": "b.py"})


def test_repeated_action_detection_uses_canonical_arguments() -> None:
    ledger = BudgetLedger(BudgetSpec(max_repeated_actions=0))
    ledger.reserve_tool_call("search", {"query": "cache", "path": "."})
    with pytest.raises(BudgetExceeded, match="repeated_actions"):
        ledger.reserve_tool_call("search", {"path": ".", "query": "cache"})


def test_time_budget_checked_before_action() -> None:
    with patch("forgemcp.core.budget.time.monotonic", side_effect=[10.0, 12.1]):
        ledger = BudgetLedger(BudgetSpec(max_wall_seconds=2.0))
        with pytest.raises(BudgetExceeded, match="wall_seconds"):
            ledger.check_time()
