"""Serializable domain models shared by the agent, tools, and MCP boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for durable events."""
    return datetime.now(UTC)


class TaskStatus(StrEnum):
    CREATED = "created"
    INDEXING = "indexing"
    PLANNING = "planning"
    ACTING = "acting"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    BLOCKED = "blocked"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Issue(BaseModel):
    """A repository issue presented to the coding agent."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=50_000)
    acceptance_criteria: list[str] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)

    @property
    def prompt(self) -> str:
        criteria = "\n".join(f"- {item}" for item in self.acceptance_criteria)
        suffix = f"\n\nAcceptance criteria:\n{criteria}" if criteria else ""
        return f"{self.title}\n\n{self.body}{suffix}"


class BudgetSpec(BaseModel):
    """Hard limits applied to one agent run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_tool_calls: int = Field(default=30, ge=1, le=500)
    max_model_calls: int = Field(default=12, ge=1, le=100)
    max_input_tokens: int = Field(default=80_000, ge=1_000)
    max_output_tokens: int = Field(default=20_000, ge=500)
    max_wall_seconds: float = Field(default=900.0, gt=0, le=14_400)
    max_repeated_actions: int = Field(default=2, ge=0, le=10)


class Usage(BaseModel):
    tool_calls: int = 0
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    wall_seconds: float = 0.0


class ToolCall(BaseModel):
    """A schema-checked tool request emitted by the model."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """A bounded observation returned to the agent loop."""

    call_id: str
    tool_name: str
    ok: bool
    output: str = ""
    error: str | None = None
    truncated: bool = False
    reference: str | None = None
    elapsed_seconds: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class TestCase(BaseModel):
    node_id: str
    outcome: Literal["passed", "failed", "error", "skipped"]
    duration_seconds: float = 0.0
    message: str | None = None


class TestReport(BaseModel):
    command: list[str]
    exit_code: int
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0
    cases: list[TestCase] = Field(default_factory=list)
    summary: str = ""

    @property
    def successful(self) -> bool:
        return self.exit_code == 0 and self.failed == 0 and self.errors == 0


class ContextSnippet(BaseModel):
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    text: str
    score: float
    reasons: list[str] = Field(default_factory=list)
    estimated_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_lines(self) -> ContextSnippet:
        if self.end_line < self.start_line:
            raise ValueError("end_line must be >= start_line")
        return self


class ContextBundle(BaseModel):
    query: str
    snippets: list[ContextSnippet] = Field(default_factory=list)
    estimated_tokens: int = 0
    omitted_candidates: int = 0
    strategy: str = "hybrid"

    def render(self) -> str:
        blocks = []
        for snippet in self.snippets:
            reasons = ", ".join(snippet.reasons)
            blocks.append(
                f"### {snippet.path}:{snippet.start_line}-{snippet.end_line} [{reasons}]\n"
                f"```\n{snippet.text}\n```"
            )
        return "\n\n".join(blocks)


class AgentDecision(BaseModel):
    """One model turn, normalized independently of any LLM provider."""

    reasoning_summary: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    final_answer: str | None = None


class RunResult(BaseModel):
    run_id: str
    status: TaskStatus
    issue: Issue
    usage: Usage
    summary: str
    changed_files: list[str] = Field(default_factory=list)
    test_report: TestReport | None = None
    patch: str = ""
    events_path: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime = Field(default_factory=utc_now)


class RunConfig(BaseModel):
    repository: Path
    model: str = "gpt-5.2"
    context_token_budget: int = Field(default=12_000, ge=1_000)
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
    approval_mode: Literal["never", "on-risk", "always"] = "on-risk"
    test_command: list[str] = Field(default_factory=lambda: ["python", "-m", "pytest", "-q"])
    allow_network: bool = False
