"""Provider-neutral model protocol and OpenAI Responses API adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from forgemcp.core.models import AgentDecision, ToolCall, ToolResult


@dataclass(frozen=True, slots=True)
class ModelTurn:
    prompt: str
    tool_definitions: list[dict[str, Any]]
    tool_results: list[ToolResult] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ModelResponse:
    decision: AgentDecision
    input_tokens: int = 0
    output_tokens: int = 0
    response_id: str | None = None


class ModelBackend(Protocol):
    def decide(self, turn: ModelTurn) -> ModelResponse: ...


SYSTEM_INSTRUCTIONS = """You are ForgeMCP, a repository coding agent.
Work from evidence. Inspect relevant code before editing. Make the smallest coherent fix.
Use only the supplied tools; paths must be repository-relative. Never modify tests merely
to hide a product defect. Run focused tests after edits, inspect failures, then run the
configured test suite. Do not claim completion until tests pass. If requirements cannot
be met within the remaining budget, explain what remains rather than inventing success.
"""


class OpenAIResponsesModel:
    """Stateful adapter using `previous_response_id` and function-call outputs."""

    def __init__(self, model: str, client: Any | None = None) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI()
        self.client = client
        self.model = model
        self.previous_response_id: str | None = None

    def decide(self, turn: ModelTurn) -> ModelResponse:
        inputs: list[dict[str, Any]] = []
        if self.previous_response_id is None:
            inputs.append({"role": "user", "content": turn.prompt})
        for result in turn.tool_results:
            content = result.output if result.ok else (result.error or "tool failed")
            inputs.append(
                {
                    "type": "function_call_output",
                    "call_id": result.call_id,
                    "output": content,
                }
            )
        if self.previous_response_id is not None and turn.prompt:
            inputs.append({"role": "user", "content": turn.prompt})

        request: dict[str, Any] = {
            "model": self.model,
            "instructions": SYSTEM_INSTRUCTIONS,
            "input": inputs,
            "tools": turn.tool_definitions,
            "parallel_tool_calls": False,
            "store": True,
        }
        if self.previous_response_id is not None:
            request["previous_response_id"] = self.previous_response_id
        response = self.client.responses.create(**request)
        self.previous_response_id = response.id

        calls: list[ToolCall] = []
        summaries: list[str] = []
        for item in response.output:
            kind = getattr(item, "type", None)
            if kind == "function_call":
                arguments = json.loads(item.arguments or "{}")
                calls.append(
                    ToolCall(
                        id=item.call_id,
                        name=item.name,
                        arguments=arguments,
                    )
                )
            elif kind == "reasoning":
                summary = getattr(item, "summary", None)
                if summary:
                    summaries.append(str(summary))

        usage = getattr(response, "usage", None)
        return ModelResponse(
            decision=AgentDecision(
                reasoning_summary="\n".join(summaries),
                tool_calls=calls,
                final_answer=response.output_text if not calls else None,
            ),
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            response_id=response.id,
        )
