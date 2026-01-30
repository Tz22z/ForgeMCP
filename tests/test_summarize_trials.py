from __future__ import annotations

import json
from pathlib import Path

from scripts.summarize_trials import render_markdown, summarize


def write_report(path: Path, strategy: str, solved: bool) -> None:
    record = {
        "instance_id": "case-1",
        "status": "succeeded",
        "solved": solved,
        "grader_exit_code": 0 if solved else 1,
        "protected_files_unchanged": True,
        "repeated_read_ratio": 0.0,
        "estimated_cost_usd": 0.01,
        "usage": {
            "tool_calls": 4,
            "model_calls": 5,
            "input_tokens": 1000,
            "output_tokens": 100,
        },
    }
    path.write_text(
        json.dumps(
            {
                "strategy": strategy,
                "model": "fixed-model",
                "records": [record],
            }
        )
    )


def test_summarize_paired_trials(tmp_path: Path) -> None:
    repository = tmp_path
    (repository / "src" / "forgemcp").mkdir(parents=True)
    (repository / "src" / "forgemcp" / "runtime.py").write_text("VERSION = 1\n")
    benchmark = repository / "benchmarks" / "small"
    benchmark.mkdir(parents=True)
    (benchmark / "fixture").mkdir()
    (benchmark / "fixture" / "source.py").write_text("VALUE = 1\n")
    (benchmark / "grader").mkdir()
    (benchmark / "grader" / "test_hidden.py").write_text("def test_ok(): pass\n")
    manifest = benchmark / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "name": "Fixture benchmark",
                "description": "A deterministic fixture.",
                "limitations": ["Synthetic only."],
                "cases": [
                    {
                        "instance_id": "case-1",
                        "fixture": "fixture",
                        "grader": "grader",
                    }
                ],
            }
        )
    )
    baseline = benchmark / "baseline.json"
    hybrid = benchmark / "hybrid.json"
    write_report(baseline, "baseline", True)
    write_report(hybrid, "hybrid", False)

    summary = summarize(
        manifest,
        [baseline],
        [hybrid],
        input_price_per_million=1.75,
        output_price_per_million=14,
        repository=repository,
    )

    assert summary["strategies"]["baseline"]["solve_rate"] == 1.0
    assert summary["strategies"]["hybrid"]["solve_rate"] == 0.0
    assert summary["comparison"]["solve_rate_change_percentage_points"] == -100.0
    markdown = render_markdown(summary)
    assert summary["experiment"] == "Fixture benchmark"
    assert summary["limitations"] == ["Synthetic only."]
    assert "Hybrid change" in markdown
    assert "100.0 percentage points lower" in markdown
