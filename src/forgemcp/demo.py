"""Deterministic offline walkthrough of a two-file verified fix."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

from forgemcp.agent.model import ModelResponse, ModelTurn
from forgemcp.agent.runtime import AgentRuntime
from forgemcp.core.models import AgentDecision, Issue, RunConfig, RunResult, ToolCall


class DemoModel:
    """Recorded decisions keep the product demo free of API cost and variance."""

    def __init__(self) -> None:
        self._decisions = deque(
            [
                AgentDecision(
                    reasoning_summary="Inspect the tier mapping first.",
                    tool_calls=[
                        ToolCall(
                            id="demo-read-1",
                            name="read_file",
                            arguments={"path": "shop/pricing.py"},
                        )
                    ],
                ),
                AgentDecision(
                    reasoning_summary="Inspect shipping eligibility at the checkout boundary.",
                    tool_calls=[
                        ToolCall(
                            id="demo-read-2",
                            name="read_file",
                            arguments={"path": "shop/checkout.py"},
                        )
                    ],
                ),
                AgentDecision(
                    reasoning_summary="Correct the Pro contract rate.",
                    tool_calls=[
                        ToolCall(
                            id="demo-edit-1",
                            name="replace_text",
                            arguments={
                                "path": "shop/pricing.py",
                                "old": '"pro": Decimal("0.05")',
                                "new": '"pro": Decimal("0.10")',
                            },
                        )
                    ],
                ),
                AgentDecision(
                    reasoning_summary="Use gross subtotal for the free-shipping threshold.",
                    tool_calls=[
                        ToolCall(
                            id="demo-edit-2",
                            name="replace_text",
                            arguments={
                                "path": "shop/checkout.py",
                                "old": "if discounted >= FREE_SHIPPING_MINIMUM",
                                "new": "if gross >= FREE_SHIPPING_MINIMUM",
                            },
                        )
                    ],
                ),
                AgentDecision(
                    reasoning_summary="Run the independent checkout tests.",
                    tool_calls=[
                        ToolCall(
                            id="demo-test-1",
                            name="run_tests",
                            arguments={"targets": ["tests/test_checkout.py"]},
                        )
                    ],
                ),
                AgentDecision(
                    final_answer=(
                        "Updated the Pro discount to 10% and based free shipping on the "
                        "pre-discount subtotal. The checkout tests pass."
                    )
                ),
            ]
        )

    def decide(self, _turn: ModelTurn) -> ModelResponse:
        if not self._decisions:
            raise RuntimeError("demo transcript exhausted")
        return ModelResponse(self._decisions.popleft(), input_tokens=320, output_tokens=80)


def run_demo(source: Path, keep: bool = False) -> tuple[RunResult, Path]:
    workspace = Path(tempfile.mkdtemp(prefix="forgemcp-demo-"))
    shutil.copytree(source, workspace, dirs_exist_ok=True)
    _initialize_repository(workspace)
    issue = Issue(
        title="Pro checkout applies the wrong contract",
        body=(
            "Pro customers receive a 10% discount. Free shipping eligibility uses the "
            "pre-discount subtotal; the final total includes the discount."
        ),
        acceptance_criteria=[
            "A $40 Pro cart receives a $4 discount",
            "A $50 Pro cart has free shipping and a $45 total",
            "Do not modify the tests",
        ],
    )
    config = RunConfig(
        repository=workspace,
        test_command=[sys.executable, "-m", "pytest", "-q"],
        approval_mode="never",
    )
    result = AgentRuntime(config, DemoModel()).run(issue)
    if not keep:
        # Keep successful workspaces long enough for CLI rendering, then callers remove them.
        pass
    return result, workspace


def cleanup_demo(workspace: Path) -> None:
    shutil.rmtree(workspace, ignore_errors=True)


def _initialize_repository(workspace: Path) -> None:
    commands = [
        ["git", "init", "-q"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=ForgeMCP Demo",
            "-c",
            "user.email=demo@forgemcp.local",
            "commit",
            "-qm",
            "buggy fixture",
        ],
    ]
    for command in commands:
        subprocess.run(command, cwd=workspace, check=True, capture_output=True, timeout=15)
