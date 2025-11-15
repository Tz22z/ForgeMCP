"""Single dispatch boundary for schema validation, policy, budget, and audit."""

from __future__ import annotations

import time
from typing import Any

from pydantic import ValidationError

from forgemcp.context.index import RepositoryIndex
from forgemcp.core.budget import BudgetLedger
from forgemcp.core.events import EventJournal
from forgemcp.core.models import ToolCall, ToolResult
from forgemcp.tools.observations import ObservationStore
from forgemcp.tools.policy import ApprovalRequired, PolicyViolation, ToolPolicy
from forgemcp.tools.toolset import TOOL_SCHEMAS, RepositoryTools


class ToolDispatcher:
    def __init__(
        self,
        tools: RepositoryTools,
        policy: ToolPolicy,
        ledger: BudgetLedger,
        journal: EventJournal,
        observations: ObservationStore,
        index: RepositoryIndex | None = None,
    ) -> None:
        self.tools = tools
        self.policy = policy
        self.ledger = ledger
        self.journal = journal
        self.observations = observations
        self.index = index

    def definitions(self) -> list[dict[str, Any]]:
        definitions = []
        for name, (schema, _risk, description) in TOOL_SCHEMAS.items():
            definitions.append(
                {
                    "type": "function",
                    "name": name,
                    "description": description,
                    "parameters": schema.model_json_schema(),
                    "strict": True,
                }
            )
        return definitions

    def dispatch(self, call: ToolCall) -> ToolResult:
        started = time.monotonic()
        try:
            if call.name not in TOOL_SCHEMAS:
                raise PolicyViolation(f"unknown tool: {call.name}")
            schema, risk, _description = TOOL_SCHEMAS[call.name]
            arguments = schema.model_validate(call.arguments)
            self.ledger.reserve_tool_call(call.name, call.arguments)
            self.policy.authorize(call.name, risk, f"requested with arguments {call.arguments}")
            self.journal.append(
                "tool.started",
                {"call_id": call.id, "name": call.name, "arguments": call.arguments, "risk": risk},
            )
            handler = getattr(self.tools, call.name)
            raw = handler(arguments)
            bounded = self.observations.bound(call.id, raw.output)
            if raw.metadata.get("mutated") and self.index is not None:
                path = str(raw.metadata["path"])
                dependents = self.index.invalidate(path)
                refreshed = self.index.refresh()
                raw.metadata["invalidated_dependents"] = dependents
                raw.metadata["index_reparsed"] = refreshed.parsed
            result = ToolResult(
                call_id=call.id,
                tool_name=call.name,
                ok=True,
                output=bounded.text,
                truncated=bounded.truncated,
                reference=bounded.reference,
                elapsed_seconds=round(time.monotonic() - started, 3),
                metadata=raw.metadata,
            )
        except (ValidationError, ApprovalRequired, PolicyViolation, OSError, ValueError) as error:
            result = ToolResult(
                call_id=call.id,
                tool_name=call.name,
                ok=False,
                error=f"{type(error).__name__}: {error}",
                elapsed_seconds=round(time.monotonic() - started, 3),
            )
        self.journal.append("tool.finished", result.model_dump(mode="json"))
        return result

