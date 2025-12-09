"""Command-line interface for indexing, running, and demonstrating ForgeMCP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from forgemcp.agent.model import OpenAIResponsesModel
from forgemcp.agent.runtime import AgentRuntime
from forgemcp.config import load_config
from forgemcp.context.index import RepositoryIndex
from forgemcp.context.selector import ContextSelector
from forgemcp.core.models import Issue, RunResult, TaskStatus
from forgemcp.demo import cleanup_demo, run_demo

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
