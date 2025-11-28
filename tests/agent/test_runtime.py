from __future__ import annotations

import subprocess
from collections import deque
from pathlib import Path

from forgemcp.agent.model import ModelResponse, ModelTurn
from forgemcp.agent.runtime import AgentRuntime
from forgemcp.core.models import (
    AgentDecision,
    BudgetSpec,
    Issue,
    RunConfig,
    TaskStatus,
    ToolCall,
)


class SequenceModel:
    def __init__(self, decisions: list[AgentDecision]) -> None:
        self.decisions = deque(decisions)
        self.turns: list[ModelTurn] = []

    def decide(self, turn: ModelTurn) -> ModelResponse:
        self.turns.append(turn)
        return ModelResponse(self.decisions.popleft(), input_tokens=10, output_tokens=5)


def git(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True, capture_output=True)


def sample_repository(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (tmp_path / "tests" / "test_calc.py").write_text(
        "import unittest\n"
        "from calc import add\n\n"
        "class AddTests(unittest.TestCase):\n"
        "    def test_add(self):\n"
        "        self.assertEqual(add(2, 3), 5)\n"
    )
    git(["git", "init", "-q"], tmp_path)
    git(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "."], tmp_path)
    git(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "initial",
        ],
        tmp_path,
    )


def config(tmp_path: Path, **budget_overrides: int) -> RunConfig:
    return RunConfig(
        repository=tmp_path,
        test_command=["python", "-m", "unittest", "discover", "-s", "tests", "-q"],
        budget=BudgetSpec(**budget_overrides),
    )


def test_runtime_requires_tests_after_mutation(tmp_path: Path) -> None:
    sample_repository(tmp_path)
    model = SequenceModel(
        [
            AgentDecision(
                tool_calls=[
                    ToolCall(
                        id="edit-1",
                        name="replace_text",
                        arguments={"path": "calc.py", "old": "a - b", "new": "a + b"},
                    )
                ]
            ),
            AgentDecision(final_answer="Fixed addition and verified the behavior."),
        ]
    )
    result = AgentRuntime(config(tmp_path), model).run(
        Issue(title="Addition is wrong", body="add(2, 3) should return 5")
    )
    assert result.status == TaskStatus.SUCCEEDED
    assert result.test_report is not None and result.test_report.successful
    assert result.changed_files == ["calc.py"]
    assert "a + b" in result.patch


def test_runtime_reports_budget_exhaustion_explicitly(tmp_path: Path) -> None:
    sample_repository(tmp_path)
    model = SequenceModel(
        [
            AgentDecision(
                tool_calls=[ToolCall(id="read-1", name="read_file", arguments={"path": "calc.py"})]
            )
        ]
    )
    result = AgentRuntime(config(tmp_path, max_model_calls=1), model).run(
        Issue(title="Inspect", body="Inspect the addition function")
    )
    assert result.status == TaskStatus.BUDGET_EXHAUSTED
    assert "model_calls" in result.summary
