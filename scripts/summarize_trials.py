"""Aggregate paired ForgeMCP evaluation trials into auditable JSON and Markdown."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_sha256(root: Path, *, excluded_parts: set[str] | None = None) -> str:
    excluded = excluded_parts or set()
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts):
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def benchmark_inputs_sha256(manifest_path: Path, repository: Path) -> str:
    """Hash the manifest plus every referenced fixture and external grader file."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256()
    paths = [manifest_path]
    for case in manifest["cases"]:
        for field in ("fixture", "grader"):
            root = (manifest_path.parent / case[field]).resolve()
            paths.extend(path for path in root.rglob("*") if path.is_file())
    excluded = {".forgemcp", ".pytest_cache", "__pycache__"}
    for path in sorted(set(paths)):
        relative = path.relative_to(repository)
        if any(part in excluded for part in relative.parts):
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_reports(paths: list[Path], expected_strategy: str) -> list[dict[str, Any]]:
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if not reports:
        raise ValueError(f"no {expected_strategy} reports supplied")
    for path, report in zip(paths, reports, strict=True):
        if report["strategy"] != expected_strategy:
            raise ValueError(
                f"{path} has strategy {report['strategy']!r}, expected {expected_strategy!r}"
            )
    return reports


def strategy_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    records = [record for report in reports for record in report["records"]]
    attempted = len(records)
    solved = sum(bool(record["solved"]) for record in records)
    total_cost = sum(float(record["estimated_cost_usd"]) for record in records)

    def total_usage(field: str) -> int:
        return sum(int(record["usage"][field]) for record in records)

    return {
        "attempted": attempted,
        "solved": solved,
        "solve_rate": round(solved / attempted, 6) if attempted else 0.0,
        "average_tool_calls": round(total_usage("tool_calls") / attempted, 6),
        "average_model_calls": round(total_usage("model_calls") / attempted, 6),
        "average_input_tokens": round(total_usage("input_tokens") / attempted, 3),
        "average_output_tokens": round(total_usage("output_tokens") / attempted, 3),
        "total_input_tokens": total_usage("input_tokens"),
        "total_output_tokens": total_usage("output_tokens"),
        "estimated_total_cost_usd": round(total_cost, 6),
        "cost_per_solved_usd": round(total_cost / solved, 6) if solved else None,
        "average_repeated_read_ratio": round(
            sum(float(record["repeated_read_ratio"]) for record in records) / attempted,
            6,
        ),
        "hidden_grader_passes": sum(int(record["grader_exit_code"]) == 0 for record in records),
        "protected_file_violations": sum(
            not bool(record["protected_files_unchanged"]) for record in records
        ),
        "non_success_terminal_states": sum(record["status"] != "succeeded" for record in records),
    }


def relative_change(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline in {None, 0}:
        return None
    return round(candidate / baseline - 1, 6)


def summarize(
    manifest_path: Path,
    baseline_paths: list[Path],
    hybrid_paths: list[Path],
    *,
    input_price_per_million: float,
    output_price_per_million: float,
    repository: Path,
) -> dict[str, Any]:
    if len(baseline_paths) != len(hybrid_paths):
        raise ValueError("baseline and hybrid trial counts differ")
    baseline_reports = load_reports(baseline_paths, "baseline")
    hybrid_reports = load_reports(hybrid_paths, "hybrid")
    all_reports = [*baseline_reports, *hybrid_reports]
    models = {str(report["model"]) for report in all_reports}
    if len(models) != 1:
        raise ValueError(f"reports use different models: {sorted(models)}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_ids = [case["instance_id"] for case in manifest["cases"]]
    manifest_hash = file_sha256(manifest_path)
    for report in all_reports:
        report_ids = [record["instance_id"] for record in report["records"]]
        if report_ids != manifest_ids:
            raise ValueError("report instance order does not match the manifest")
        if report.get("manifest_sha256") not in {None, manifest_hash}:
            raise ValueError("report manifest hash does not match the supplied manifest")
        expected_pricing = {
            "input_per_million": input_price_per_million,
            "output_per_million": output_price_per_million,
        }
        if report.get("pricing") not in (None, expected_pricing):
            raise ValueError("report pricing does not match the supplied prices")

    baseline = strategy_summary(baseline_reports)
    hybrid = strategy_summary(hybrid_reports)
    trials: list[dict[str, Any]] = []
    for number, (base_report, hybrid_report) in enumerate(
        zip(baseline_reports, hybrid_reports, strict=True), start=1
    ):
        trials.append(
            {
                "trial": number,
                "baseline": strategy_summary([base_report]),
                "hybrid": strategy_summary([hybrid_report]),
            }
        )

    per_instance: dict[str, dict[str, Any]] = {}
    for instance_id in manifest_ids:
        per_instance[instance_id] = {}
        for strategy, reports in (
            ("baseline", baseline_reports),
            ("hybrid", hybrid_reports),
        ):
            records = [
                next(record for record in report["records"] if record["instance_id"] == instance_id)
                for report in reports
            ]
            per_instance[instance_id][strategy] = {
                "solved": sum(bool(record["solved"]) for record in records),
                "attempted": len(records),
                "protected_file_violations": sum(
                    not bool(record["protected_files_unchanged"]) for record in records
                ),
            }

    try:
        git_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        git_head = "unavailable"

    sources = []
    for strategy, paths in (("baseline", baseline_paths), ("hybrid", hybrid_paths)):
        for trial, path in enumerate(paths, start=1):
            sources.append(
                {
                    "strategy": strategy,
                    "trial": trial,
                    "path": path.relative_to(repository).as_posix(),
                    "sha256": file_sha256(path),
                }
            )

    comparison = {
        "solve_rate_change_percentage_points": round(
            (hybrid["solve_rate"] - baseline["solve_rate"]) * 100, 3
        ),
        "average_tool_calls_relative_change": relative_change(
            hybrid["average_tool_calls"], baseline["average_tool_calls"]
        ),
        "average_model_calls_relative_change": relative_change(
            hybrid["average_model_calls"], baseline["average_model_calls"]
        ),
        "average_input_tokens_relative_change": relative_change(
            hybrid["average_input_tokens"], baseline["average_input_tokens"]
        ),
        "average_output_tokens_relative_change": relative_change(
            hybrid["average_output_tokens"], baseline["average_output_tokens"]
        ),
        "average_repeated_read_ratio_change_percentage_points": round(
            (hybrid["average_repeated_read_ratio"] - baseline["average_repeated_read_ratio"]) * 100,
            3,
        ),
        "estimated_total_cost_relative_change": relative_change(
            hybrid["estimated_total_cost_usd"], baseline["estimated_total_cost_usd"]
        ),
        "cost_per_solved_relative_change": relative_change(
            hybrid["cost_per_solved_usd"], baseline["cost_per_solved_usd"]
        ),
    }

    return {
        "schema_version": 1,
        "experiment": manifest.get("name", "ForgeMCP baseline vs hybrid"),
        "description": manifest.get("description", "Paired ForgeMCP benchmark."),
        "generated_at": datetime.now(UTC).isoformat(),
        "model": next(iter(models)),
        "pricing_per_million_tokens_usd": {
            "input": input_price_per_million,
            "output": output_price_per_million,
        },
        "trial_count": len(baseline_reports),
        "cases_per_trial": len(manifest_ids),
        "manifest": {
            "path": manifest_path.relative_to(repository).as_posix(),
            "sha256": manifest_hash,
            "benchmark_inputs_sha256": benchmark_inputs_sha256(manifest_path, repository),
            "benchmark_tree_sha256": tree_sha256(
                manifest_path.parent,
                excluded_parts={"results", ".forgemcp", ".pytest_cache", "__pycache__"},
            ),
        },
        "runtime": {
            "git_head": git_head,
            "source_tree_sha256": tree_sha256(repository / "src" / "forgemcp"),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "strategies": {"baseline": baseline, "hybrid": hybrid},
        "comparison": comparison,
        "trials": trials,
        "per_instance": per_instance,
        "source_reports": sources,
        "limitations": manifest.get(
            "limitations",
            ["This benchmark is a regression signal, not a population estimate."],
        ),
    }


def render_markdown(summary: dict[str, Any]) -> str:
    baseline = summary["strategies"]["baseline"]
    hybrid = summary["strategies"]["hybrid"]
    comparison = summary["comparison"]
    pricing = summary["pricing_per_million_tokens_usd"]
    terminal_delta = hybrid["non_success_terminal_states"] - baseline["non_success_terminal_states"]

    def percent(value: float) -> str:
        return f"{value:.1%}"

    def relative(value: float | None) -> str:
        return "n/a" if value is None else f"{value:+.1%}"

    def money(value: float | None) -> str:
        return "n/a" if value is None else f"${value:.4f}"

    lines = [
        f"# {summary['experiment']} report",
        "",
        summary["description"],
        "",
        f"- Model: `{summary['model']}`",
        f"- Trials: {summary['trial_count']} paired trials x {summary['cases_per_trial']} cases",
        f"- Manifest SHA-256: `{summary['manifest']['sha256']}`",
        f"- Benchmark inputs SHA-256: `{summary['manifest']['benchmark_inputs_sha256']}`",
        f"- Runtime source SHA-256: `{summary['runtime']['source_tree_sha256']}`",
        (
            f"- Pricing: ${pricing['input']:g}/M input tokens and "
            f"${pricing['output']:g}/M output tokens"
        ),
        "",
        "## Aggregate results",
        "",
        "| Metric | Baseline | Hybrid | Hybrid change |",
        "| --- | ---: | ---: | ---: |",
        (
            f"| Solve rate | {baseline['solved']}/{baseline['attempted']} "
            f"({percent(baseline['solve_rate'])}) | {hybrid['solved']}/{hybrid['attempted']} "
            f"({percent(hybrid['solve_rate'])}) | "
            f"{comparison['solve_rate_change_percentage_points']:+.1f} pp |"
        ),
        (
            f"| Average tool calls | {baseline['average_tool_calls']:.2f} | "
            f"{hybrid['average_tool_calls']:.2f} | "
            f"{relative(comparison['average_tool_calls_relative_change'])} |"
        ),
        (
            f"| Average model calls | {baseline['average_model_calls']:.2f} | "
            f"{hybrid['average_model_calls']:.2f} | "
            f"{relative(comparison['average_model_calls_relative_change'])} |"
        ),
        (
            f"| Average input tokens | {baseline['average_input_tokens']:.0f} | "
            f"{hybrid['average_input_tokens']:.0f} | "
            f"{relative(comparison['average_input_tokens_relative_change'])} |"
        ),
        (
            f"| Average repeated-read ratio | "
            f"{percent(baseline['average_repeated_read_ratio'])} | "
            f"{percent(hybrid['average_repeated_read_ratio'])} | "
            f"{comparison['average_repeated_read_ratio_change_percentage_points']:+.1f} pp |"
        ),
        (
            f"| Estimated total cost | ${baseline['estimated_total_cost_usd']:.4f} | "
            f"${hybrid['estimated_total_cost_usd']:.4f} | "
            f"{relative(comparison['estimated_total_cost_relative_change'])} |"
        ),
        (
            f"| Cost per solve | {money(baseline['cost_per_solved_usd'])} | "
            f"{money(hybrid['cost_per_solved_usd'])} | "
            f"{relative(comparison['cost_per_solved_relative_change'])} |"
        ),
        (
            f"| Protected-file violations | {baseline['protected_file_violations']} | "
            f"{hybrid['protected_file_violations']} | "
            f"{hybrid['protected_file_violations'] - baseline['protected_file_violations']:+d} |"
        ),
        (
            f"| Hidden grader passes | {baseline['hidden_grader_passes']}/"
            f"{baseline['attempted']} | {hybrid['hidden_grader_passes']}/"
            f"{hybrid['attempted']} | "
            f"{hybrid['hidden_grader_passes'] - baseline['hidden_grader_passes']:+d} |"
        ),
        (
            f"| Non-success terminal states | {baseline['non_success_terminal_states']} | "
            f"{hybrid['non_success_terminal_states']} | "
            f"{terminal_delta:+d} |"
        ),
        "",
        "## Paired trials",
        "",
        "| Trial | Baseline solved | Hybrid solved | Baseline cost | Hybrid cost |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for trial in summary["trials"]:
        base_trial = trial["baseline"]
        hybrid_trial = trial["hybrid"]
        lines.append(
            f"| {trial['trial']} | {base_trial['solved']}/{base_trial['attempted']} | "
            f"{hybrid_trial['solved']}/{hybrid_trial['attempted']} | "
            f"${base_trial['estimated_total_cost_usd']:.4f} | "
            f"${hybrid_trial['estimated_total_cost_usd']:.4f} |"
        )

    lines.extend(["", "## Interpretation", ""])
    solve_delta = comparison["solve_rate_change_percentage_points"]
    if solve_delta == 0:
        lines.append("Both strategies achieved the same aggregate solve rate.")
    else:
        direction = "higher" if solve_delta > 0 else "lower"
        lines.append(
            f"Hybrid's aggregate solve rate was {abs(solve_delta):.1f} percentage points "
            f"{direction} than baseline."
        )
    lines.extend(
        [
            "",
            (
                "Relative to baseline, hybrid changed average tool calls by "
                f"{relative(comparison['average_tool_calls_relative_change'])}, model calls by "
                f"{relative(comparison['average_model_calls_relative_change'])}, input tokens by "
                f"{relative(comparison['average_input_tokens_relative_change'])}, and estimated "
                f"total cost by {relative(comparison['estimated_total_cost_relative_change'])}."
            ),
        ]
    )
    total_violations = baseline["protected_file_violations"] + hybrid["protected_file_violations"]
    if total_violations:
        lines.extend(
            [
                "",
                (
                    f"The anti-tampering rule rejected {total_violations} run(s) that changed "
                    "protected visible tests, regardless of hidden-grader outcome."
                ),
            ]
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in summary["limitations"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, nargs="+", required=True)
    parser.add_argument("--hybrid", type=Path, nargs="+", required=True)
    parser.add_argument("--input-price-per-million", type=float, required=True)
    parser.add_argument("--output-price-per-million", type=float, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    repository = Path.cwd().resolve()
    summary = summarize(
        args.manifest.resolve(),
        [path.resolve() for path in args.baseline],
        [path.resolve() for path in args.hybrid],
        input_price_per_million=args.input_price_per_million,
        output_price_per_million=args.output_price_per_million,
        repository=repository,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.write_text(render_markdown(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
