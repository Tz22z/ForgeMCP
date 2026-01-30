"""Command-line interface for indexing, running, and demonstrating ForgeMCP."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from forgemcp import __version__
from forgemcp.agent.model import OpenAIResponsesModel
from forgemcp.agent.runtime import AgentRuntime
from forgemcp.config import load_config
from forgemcp.context.index import RepositoryIndex
from forgemcp.context.selector import ContextSelector
from forgemcp.core.models import Issue, RunResult, TaskStatus
from forgemcp.demo import cleanup_demo, run_demo
from forgemcp.evaluation.harness import (
    EvaluationHarness,
    load_manifest,
    normalize_test_command,
    write_report,
)
from forgemcp.evaluation.models import EvaluationCase, Pricing

app = typer.Typer(no_args_is_help=True, help="Verified repository-level coding agent")
console = Console()


@app.command("index")
def index_repository(
    repository: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
) -> None:
    """Build or refresh the incremental repository index."""
    index = RepositoryIndex(repository)
    stats = index.refresh()
    console.print(
        f"Indexed [bold]{stats.discovered}[/] files: {stats.parsed} parsed, "
        f"{stats.unchanged} unchanged, {stats.removed} removed, {stats.symbols} symbols updated."
    )


@app.command("context")
def preview_context(
    issue: Annotated[str, typer.Argument(help="Issue text used to rank repository context")],
    repository: Annotated[Path, typer.Option("--repo", exists=True, file_okay=False)] = Path("."),
    tokens: Annotated[int, typer.Option("--tokens", min=200)] = 4_000,
) -> None:
    """Preview context selected under a token budget without calling a model."""
    index = RepositoryIndex(repository)
    index.refresh()
    bundle = ContextSelector(index).select(issue, token_budget=tokens)
    table = Table(
        "Score", "File", "Reasons", title=f"Selected context · ~{bundle.estimated_tokens} tokens"
    )
    for snippet in bundle.snippets:
        table.add_row(f"{snippet.score:.2f}", snippet.path, ", ".join(snippet.reasons))
    console.print(table)


@app.command("run")
def run_issue(
    issue_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    repository: Annotated[Path, typer.Option("--repo", exists=True, file_okay=False)] = Path("."),
    model: Annotated[str | None, typer.Option("--model")] = None,
    docker: Annotated[bool, typer.Option("--docker/--local")] = False,
) -> None:
    """Run a live OpenAI-backed coding task from a Markdown or JSON issue file."""
    issue = _load_issue(issue_file)
    config = load_config(repository)
    if model:
        config.model = model
    if docker:
        config.execution_mode = "docker"
    result = AgentRuntime(config, OpenAIResponsesModel(config.model)).run(issue)
    _render_result(result)
    raise typer.Exit(0 if result.status == TaskStatus.SUCCEEDED else 1)


@app.command("demo")
def demo(
    keep: Annotated[
        bool, typer.Option("--keep", help="Keep the temporary fixed repository")
    ] = False,
) -> None:
    """Run an API-free two-file bug-fix demo with real tests."""
    source = Path(__file__).resolve().parents[2] / "examples" / "demo_shop"
    if not source.exists():
        raise typer.BadParameter("demo fixture is available from a source checkout")
    result, workspace = run_demo(source, keep=keep)
    _render_result(result)
    if keep:
        console.print(f"Demo workspace: [link=file://{workspace}]{workspace}[/link]")
    else:
        cleanup_demo(workspace)
    raise typer.Exit(0 if result.status == TaskStatus.SUCCEEDED else 1)


@app.command("serve")
def serve() -> None:
    """Start the ForgeMCP stdio MCP server."""
    from forgemcp.server import mcp

    mcp.run()


@app.command("evaluate")
def evaluate(
    manifest: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    strategy: Annotated[str, typer.Option("--strategy")] = "hybrid",
    model: Annotated[str, typer.Option("--model")] = "gpt-5.2",
    report_path: Annotated[Path, typer.Option("--output")] = Path("artifacts/evaluation.json"),
    input_price: Annotated[float, typer.Option("--input-price-per-million", min=0)] = 0.0,
    output_price: Annotated[float, typer.Option("--output-price-per-million", min=0)] = 0.0,
) -> None:
    """Run a fixed manifest using one context strategy and an external grader."""
    if strategy not in {"baseline", "hybrid"}:
        raise typer.BadParameter("strategy must be baseline or hybrid")
    cases = load_manifest(manifest)

    def run_case(repository: Path, case: EvaluationCase, selected_strategy: str) -> RunResult:
        config = load_config(repository)
        config.model = model
        config.context_strategy = "baseline" if selected_strategy == "baseline" else "hybrid"
        config.test_command = normalize_test_command(case.test_command)
        return AgentRuntime(config, OpenAIResponsesModel(model)).run(case.issue)

    harness = EvaluationHarness(
        run_case,
        model=model,
        pricing=Pricing(
            input_per_million=input_price,
            output_per_million=output_price,
        ),
    )
    report = harness.run(cases, strategy)
    report.manifest_sha256 = hashlib.sha256(manifest.read_bytes()).hexdigest()
    report.environment = {
        "forgemcp": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    write_report(report, report_path)
    table = Table("Metric", "Value", title=f"Evaluation · {strategy}")
    table.add_row("Solved", f"{report.solved}/{report.attempted}")
    table.add_row("Solve rate", f"{report.solve_rate:.1%}")
    table.add_row("Average tool calls", f"{report.average_tool_calls:.2f}")
    table.add_row("Repeated read ratio", f"{report.average_repeated_read_ratio:.1%}")
    table.add_row("Estimated cost", f"${report.estimated_total_cost_usd:.4f}")
    console.print(table)
    console.print(f"Report: {report_path.resolve()}")


def _load_issue(path: Path) -> Issue:
    if path.suffix.lower() == ".json":
        return Issue.model_validate(json.loads(path.read_text(encoding="utf-8")))
    text = path.read_text(encoding="utf-8").strip()
    lines = text.splitlines()
    title = lines[0].removeprefix("# ").strip() if lines else path.stem
    return Issue(title=title, body="\n".join(lines[1:]).strip() or text)


def _render_result(result: RunResult) -> None:
    color = "green" if result.status == TaskStatus.SUCCEEDED else "red"
    console.print(
        Panel(result.summary or "No model summary", title=f"[{color}]{result.status.value}[/]")
    )
    table = Table("Metric", "Value", show_header=False)
    table.add_row("Run", result.run_id)
    table.add_row("Files changed", str(len(result.changed_files)))
    table.add_row("Tool calls", str(result.usage.tool_calls))
    table.add_row("Model calls", str(result.usage.model_calls))
    table.add_row(
        "Input / output tokens", f"{result.usage.input_tokens} / {result.usage.output_tokens}"
    )
    if result.test_report:
        table.add_row("Tests", "passed" if result.test_report.successful else "failed")
    console.print(table)
    if result.patch:
        console.print(Syntax(result.patch, "diff", theme="ansi_dark", line_numbers=False))


if __name__ == "__main__":
    app()
