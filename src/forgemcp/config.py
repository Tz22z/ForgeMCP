"""Configuration loading with explicit environment-variable overrides."""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path
from typing import Any

from forgemcp.core.models import BudgetSpec, RunConfig


def load_config(repository: Path, config_path: Path | None = None) -> RunConfig:
    """Load `.forgemcp.toml`, then apply supported environment overrides."""
    source = config_path or repository / ".forgemcp.toml"
    raw: dict[str, Any] = {}
    if source.exists():
        with source.open("rb") as handle:
            raw = tomllib.load(handle)

    agent = raw.get("agent", {})
    budget_data = raw.get("budget", {})
    tools = raw.get("tools", {})
    model = os.getenv("FORGEMCP_MODEL", agent.get("model", "gpt-5.2"))

    return RunConfig(
        repository=repository.resolve(),
        model=model,
        context_token_budget=int(agent.get("context_token_budget", 12_000)),
        approval_mode=tools.get("approval_mode", "on-risk"),
        allow_network=bool(tools.get("allow_network", False)),
        test_command=list(tools.get("test_command", [sys.executable, "-m", "pytest", "-q"])),
        execution_mode=tools.get("execution_mode", "local"),
        docker_image=tools.get("docker_image", "forgemcp:latest"),
        cpu_limit=float(tools.get("cpu_limit", 2.0)),
        memory_mb=int(tools.get("memory_mb", 2_048)),
        pids_limit=int(tools.get("pids_limit", 256)),
        budget=BudgetSpec(**budget_data),
    )
