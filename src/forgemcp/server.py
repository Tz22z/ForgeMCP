"""MCP server exposing ForgeMCP's indexed, verified coding workflow."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from forgemcp.agent.model import OpenAIResponsesModel
from forgemcp.agent.runtime import AgentRuntime
from forgemcp.config import load_config
from forgemcp.context.index import RepositoryIndex
from forgemcp.context.selector import ContextSelector
from forgemcp.core.models import Issue

mcp = MCPServer(
    "ForgeMCP",
    instructions=(
        "Repository-level coding agent. Index and preview context before running an issue. "
        "forge_run_issue can modify files and execute the configured tests."
    ),
)


def server_root() -> Path:
    return Path(os.getenv("FORGEMCP_ROOT", ".")).resolve()


def resolve_repository(relative_path: str = ".") -> Path:
    requested = Path(relative_path)
    if requested.is_absolute():
        raise ValueError("repository must be relative to FORGEMCP_ROOT")
    resolved = (server_root() / requested).resolve()
    if not resolved.is_relative_to(server_root()):
        raise ValueError("repository escapes FORGEMCP_ROOT")
    if not resolved.is_dir():
        raise ValueError(f"repository directory does not exist: {relative_path}")
    return resolved


@mcp.tool()
def forge_index(repository: str = ".") -> dict[str, Any]:
    """Refresh the incremental symbol and dependency index for a repository."""
    index = RepositoryIndex(resolve_repository(repository))
    stats = index.refresh()
    return {
        "discovered": stats.discovered,
        "parsed": stats.parsed,
        "unchanged": stats.unchanged,
        "removed": stats.removed,
        "symbols_updated": stats.symbols,
    }


@mcp.tool()
def forge_select_context(
    issue: str,
    repository: str = ".",
    token_budget: int = 4_000,
    failure_output: str = "",
) -> dict[str, Any]:
    """Preview files selected by lexical, symbol, dependency, diff, and failure signals."""
    if not 200 <= token_budget <= 100_000:
        raise ValueError("token_budget must be between 200 and 100000")
    index = RepositoryIndex(resolve_repository(repository))
    index.refresh()
    bundle = ContextSelector(index).select(
        issue,
        token_budget=token_budget,
        failure_output=failure_output,
    )
    return bundle.model_dump()


@mcp.tool()
async def forge_run_issue(
    title: str,
    body: str,
    repository: str = ".",
    acceptance_criteria: list[str] | None = None,
    model: str | None = None,
    use_docker: bool = True,
) -> dict[str, Any]:
    """Modify a repository to solve an issue, then require the configured tests to pass."""
    root = resolve_repository(repository)
    config = load_config(root)
    if model:
        config.model = model
    config.execution_mode = "docker" if use_docker else "local"
    issue = Issue(
        title=title,
        body=body,
        acceptance_criteria=acceptance_criteria or [],
    )
    runtime = AgentRuntime(config, OpenAIResponsesModel(config.model))
    result = await asyncio.to_thread(runtime.run, issue)
    return result.model_dump(mode="json")


@mcp.tool()
def forge_inspect_run(run_id: str, repository: str = ".") -> dict[str, Any]:
    """Read a completed run's final event and compact event timeline."""
    if not run_id.isalnum() or len(run_id) > 64:
        raise ValueError("invalid run_id")
    root = resolve_repository(repository)
    events_path = root / ".forgemcp" / "runs" / run_id / "events.jsonl"
    if not events_path.is_file():
        raise ValueError(f"run not found: {run_id}")
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    return {
        "run_id": run_id,
        "event_count": len(events),
        "timeline": [
            {
                "sequence": event["sequence"],
                "kind": event["kind"],
                "timestamp": event["timestamp"],
            }
            for event in events
        ],
        "result": events[-1]["payload"]
        if events and events[-1]["kind"] == "run.finished"
        else None,
    }


if __name__ == "__main__":
    mcp.run()
