from __future__ import annotations

from pathlib import Path

from forgemcp.core.models import Issue, RunResult, TaskStatus, Usage
from forgemcp.evaluation.harness import EvaluationHarness, normalize_test_command, run_grader
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


def result(
    workspace: Path,
    changed: list[str],
    status: TaskStatus = TaskStatus.SUCCEEDED,
) -> RunResult:
    issue = Issue(title="Double is broken", body="double must multiply by two")
    return RunResult(
        run_id="eval",
        status=status,
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
    assert report.records[0].agent_summary == "done"


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


def test_failed_agent_status_never_counts_as_solve(tmp_path: Path) -> None:
    evaluation_case = case(tmp_path)

    def fix_but_fail(workspace: Path, _case: EvaluationCase, _strategy: str) -> RunResult:
        (workspace / "app.py").write_text("def double(value):\n    return value * 2\n")
        return result(workspace, ["app.py"], TaskStatus.FAILED)

    record = (
        EvaluationHarness(fix_but_fail, model="fixed-model")
        .run([evaluation_case], "hybrid")
        .records[0]
    )
    assert record.grader_exit_code == 0
    assert not record.solved


def test_external_grader_cannot_be_shadowed_by_workspace_pytest(tmp_path: Path) -> None:
    evaluation_case = case(tmp_path)
    (tmp_path / "fixture" / "app.py").write_text("def double(value):\n    return value * 2\n")
    (tmp_path / "fixture" / "pytest.py").write_text("raise RuntimeError('shadowed')\n")

    exit_code, _summary = run_grader(evaluation_case.grader, evaluation_case.fixture)

    assert exit_code == 0


def test_pytest_command_uses_current_interpreter_in_isolated_mode() -> None:
    command = normalize_test_command(["python", "-m", "pytest", "-q"])
    assert command[:3] == [__import__("sys").executable, "-I", "-c"]
    assert command[-1] == "-q"
