from __future__ import annotations

from pathlib import Path

from forgemcp.core.models import Issue, RunResult, TaskStatus, Usage
from forgemcp.evaluation.harness import EvaluationHarness
from forgemcp.evaluation.models import EvaluationCase, Pricing


def case(tmp_path: Path) -> EvaluationCase:
    fixture = tmp_path / "fixture"
    grader = tmp_path / "grader"
    (fixture / "tests").mkdir(parents=True)
    grader.mkdir()
    (fixture / "app.py").write_text("def double(value):\n    return value\n")
    (fixture / "tests" / "test_app.py").write_text(
        "from app import double\n\ndef test_double():\n    assert double(2) == 4\n"
    )
    (grader / "test_hidden.py").write_text(
        "from app import double\n\ndef test_negative():\n    assert double(-3) == -6\n"
    )
    return EvaluationCase(
        instance_id="double-1",
        fixture=fixture,
        grader=grader,
        issue=Issue(title="Double is broken", body="double must multiply by two"),
    )


def result(workspace: Path, changed: list[str]) -> RunResult:
    issue = Issue(title="Double is broken", body="double must multiply by two")
    return RunResult(
        run_id="eval",
        status=TaskStatus.SUCCEEDED,
        issue=issue,
        usage=Usage(tool_calls=4, model_calls=2, input_tokens=1_000, output_tokens=200),
        summary="done",
        changed_files=changed,
    )


def test_hidden_grader_counts_real_fix(tmp_path: Path) -> None:
    evaluation_case = case(tmp_path)

    def fix(workspace: Path, _case: EvaluationCase, _strategy: str) -> RunResult:
        (workspace / "app.py").write_text("def double(value):\n    return value * 2\n")
        return result(workspace, ["app.py"])

    report = EvaluationHarness(
        fix,
        model="fixed-model",
        pricing=Pricing(input_per_million=1.0, output_per_million=2.0),
    ).run([evaluation_case], "hybrid")
    assert report.solved == 1
    assert report.solve_rate == 1.0
    assert report.estimated_total_cost_usd == 0.0014


def test_modifying_public_tests_never_counts_as_solve(tmp_path: Path) -> None:
    evaluation_case = case(tmp_path)

    def cheat(workspace: Path, _case: EvaluationCase, _strategy: str) -> RunResult:
        (workspace / "tests" / "test_app.py").write_text("def test_nothing():\n    pass\n")
        return result(workspace, ["tests/test_app.py"])

    record = (
        EvaluationHarness(cheat, model="fixed-model").run([evaluation_case], "baseline").records[0]
    )
    assert not record.solved
    assert not record.protected_files_unchanged
    assert record.grader_exit_code != 0
