"""Schemas for fixed evaluation manifests and aggregate reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from forgemcp.core.models import Issue, TaskStatus, Usage, utc_now


class EvaluationCase(BaseModel):
    instance_id: str
    fixture: Path
    grader: Path
    issue: Issue
    test_command: list[str] = Field(default_factory=lambda: ["python", "-m", "pytest", "-q"])


class Pricing(BaseModel):
    input_per_million: float = Field(default=0.0, ge=0)
    output_per_million: float = Field(default=0.0, ge=0)

    def cost(self, usage: Usage) -> float:
        return round(
            usage.input_tokens * self.input_per_million / 1_000_000
            + usage.output_tokens * self.output_per_million / 1_000_000,
            6,
        )


class EvaluationRecord(BaseModel):
    instance_id: str
    strategy: str
    status: TaskStatus
    agent_summary: str = ""
    solved: bool
    grader_exit_code: int
    grader_summary: str
    protected_files_unchanged: bool
    usage: Usage
    estimated_cost_usd: float
    repeated_read_ratio: float = 0.0
    changed_files: list[str] = Field(default_factory=list)


class AggregateReport(BaseModel):
    strategy: str
    model: str
    pricing: Pricing = Field(default_factory=Pricing)
    manifest_sha256: str | None = None
    environment: dict[str, str] = Field(default_factory=dict)
    attempted: int
    solved: int
    solve_rate: float
    total_tool_calls: int
    average_tool_calls: float
    total_model_calls: int
    total_input_tokens: int
    total_output_tokens: int
    estimated_total_cost_usd: float
    cost_per_solved_usd: float | None
    average_repeated_read_ratio: float
    generated_at: datetime = Field(default_factory=utc_now)
    records: list[EvaluationRecord] = Field(default_factory=list)
