"""Evaluation harness that keeps grading tests outside the agent workspace."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path

from forgemcp.context.index import RepositoryIndex
from forgemcp.core.models import RunResult
from forgemcp.evaluation.models import (
    AggregateReport,
    EvaluationCase,
    EvaluationRecord,
    Pricing,
)

AgentFactory = Callable[[Path, EvaluationCase, str], RunResult]


class EvaluationHarness:
    def __init__(
        self,
        agent: AgentFactory,
        *,
        model: str,
        pricing: Pricing | None = None,
    ) -> None:
        self.agent = agent
        self.model = model
        self.pricing = pricing or Pricing()

    def run(self, cases: Iterable[EvaluationCase], strategy: str) -> AggregateReport:
        records = [self._run_case(case, strategy) for case in cases]
        solved = sum(record.solved for record in records)
        tool_calls = sum(record.usage.tool_calls for record in records)
        model_calls = sum(record.usage.model_calls for record in records)
        input_tokens = sum(record.usage.input_tokens for record in records)
        output_tokens = sum(record.usage.output_tokens for record in records)
        total_cost = round(sum(record.estimated_cost_usd for record in records), 6)
        attempted = len(records)
        return AggregateReport(
            strategy=strategy,
            model=self.model,
            attempted=attempted,
            solved=solved,
            solve_rate=round(solved / attempted, 4) if attempted else 0.0,
            total_tool_calls=tool_calls,
            average_tool_calls=round(tool_calls / attempted, 3) if attempted else 0.0,
            total_model_calls=model_calls,
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            estimated_total_cost_usd=total_cost,
            cost_per_solved_usd=round(total_cost / solved, 6) if solved else None,
            average_repeated_read_ratio=(
                round(sum(record.repeated_read_ratio for record in records) / attempted, 4)
                if attempted
                else 0.0
            ),
            records=records,
        )

    def _run_case(self, case: EvaluationCase, strategy: str) -> EvaluationRecord:
        workspace = Path(tempfile.mkdtemp(prefix=f"forgemcp-eval-{case.instance_id}-"))
        try:
            shutil.copytree(case.fixture, workspace, dirs_exist_ok=True)
            before = protected_snapshot(workspace)
            initialize_git(workspace)
            result = self.agent(workspace, case, strategy)
            after = protected_snapshot(workspace)
            protected_unchanged = before == after
            exit_code, summary = run_grader(case.grader, workspace)
            metrics = RepositoryIndex(workspace).read_metrics()
            solved = exit_code == 0 and protected_unchanged
            return EvaluationRecord(
                instance_id=case.instance_id,
                strategy=strategy,
                status=result.status,
                solved=solved,
                grader_exit_code=exit_code,
                grader_summary=summary,
                protected_files_unchanged=protected_unchanged,
                usage=result.usage,
                estimated_cost_usd=self.pricing.cost(result.usage),
                repeated_read_ratio=float(metrics["repeated_read_ratio"]),
                changed_files=result.changed_files,
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


def load_manifest(path: Path) -> list[EvaluationCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent.resolve()
    cases = []
    for item in raw["cases"]:
        item["fixture"] = (base / item["fixture"]).resolve()
        item["grader"] = (base / item["grader"]).resolve()
        cases.append(EvaluationCase.model_validate(item))
    return cases


def write_report(report: AggregateReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def protected_snapshot(workspace: Path) -> dict[str, str]:
    """Hash visible tests so test tampering cannot count as a solve."""
    snapshot: dict[str, str] = {}
    for directory in ("tests", "test"):
        root = workspace / directory
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                snapshot[path.relative_to(workspace).as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    return snapshot


def run_grader(grader: Path, workspace: Path) -> tuple[int, str]:
    if not grader.exists():
        raise FileNotFoundError(f"grader not found: {grader}")
    process = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(grader)],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
        env={
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "PYTHONPATH": str(workspace),
            "LANG": "C.UTF-8",
        },
    )
    output = process.stdout + ("\n" + process.stderr if process.stderr else "")
    lines = [line for line in output.splitlines() if line.strip()]
    return process.returncode, lines[-1][:1_000] if lines else ""


def initialize_git(workspace: Path) -> None:
    commands = [
        ["git", "init", "-q"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=ForgeMCP Eval",
            "-c",
            "user.email=eval@forgemcp.local",
            "commit",
            "-qm",
            "evaluation fixture",
        ],
    ]
    for command in commands:
        subprocess.run(command, cwd=workspace, check=True, capture_output=True, timeout=20)
