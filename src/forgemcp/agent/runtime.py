"""Plan–act–verify loop with hard completion and budget semantics."""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from forgemcp.agent.model import ModelBackend, ModelTurn
from forgemcp.agent.prompts import continuation_prompt, initial_prompt
from forgemcp.context.index import RepositoryIndex
from forgemcp.context.selector import ContextSelector
from forgemcp.core.budget import BudgetExceeded, BudgetLedger
from forgemcp.core.events import EventJournal
from forgemcp.core.models import (
    Issue,
    RunConfig,
    RunResult,
    TaskStatus,
    TestReport,
    ToolCall,
    ToolResult,
)
from forgemcp.core.state import TaskStateMachine
from forgemcp.sandbox.runners import DockerCommandRunner, LocalCommandRunner
from forgemcp.tools.dispatcher import ToolDispatcher
from forgemcp.tools.observations import ObservationStore
from forgemcp.tools.policy import ToolPolicy
from forgemcp.tools.toolset import RepositoryTools, RunTestsArgs


class AgentRuntime:
    def __init__(self, config: RunConfig, model: ModelBackend) -> None:
        self.config = config
        self.model = model

    def run(self, issue: Issue) -> RunResult:
        run_id = uuid.uuid4().hex[:12]
        started = datetime.now(UTC)
        run_dir = self.config.repository / ".forgemcp" / "runs" / run_id
        journal = EventJournal(run_dir / "events.jsonl", run_id)
        state = TaskStateMachine()
        ledger = BudgetLedger(self.config.budget)
        index = RepositoryIndex(self.config.repository)
        selector = ContextSelector(index)
        policy = ToolPolicy(
            self.config.repository,
            approval_mode=self.config.approval_mode,
        )
        runner = (
            DockerCommandRunner(
                self.config.docker_image,
                cpus=self.config.cpu_limit,
                memory_mb=self.config.memory_mb,
                pids_limit=self.config.pids_limit,
                allow_network=self.config.allow_network,
            )
            if self.config.execution_mode == "docker"
            else LocalCommandRunner()
        )
        repository_tools = RepositoryTools(policy, self.config.test_command, runner)
        dispatcher = ToolDispatcher(
            repository_tools,
            policy,
            ledger,
            journal,
            ObservationStore(run_dir / "observations"),
            index,
        )
        latest_tests: TestReport | None = None
        mutation_generation = 0
        verified_generation = -1
        pending_results: list[ToolResult] = []
        failure_output = ""
        final_summary = ""

        journal.append(
            "run.started",
            {"issue": issue.model_dump(), "config": config_for_log(self.config)},
        )
        try:
            state.transition(TaskStatus.INDEXING)
            stats = index.refresh()
            journal.append("index.refreshed", asdict(stats))
            context = selector.select(
                issue.prompt,
                token_budget=self.config.context_token_budget,
            )
            journal.append(
                "context.selected",
                {
                    "paths": [item.path for item in context.snippets],
                    "estimated_tokens": context.estimated_tokens,
                    "strategy": context.strategy,
                },
            )
            state.transition(TaskStatus.PLANNING)
            next_prompt = initial_prompt(issue, context, self.config.budget)

            while not state.terminal:
                ledger.reserve_model_call()
                journal.append("model.started", {"usage": ledger.usage.model_dump()})
                response = self.model.decide(
                    ModelTurn(
                        prompt=next_prompt,
                        tool_definitions=dispatcher.definitions(),
                        tool_results=pending_results,
                    )
                )
                ledger.record_tokens(response.input_tokens, response.output_tokens)
                decision = response.decision
                journal.append(
                    "model.finished",
                    {
                        "response_id": response.response_id,
                        "tool_names": [call.name for call in decision.tool_calls],
                        "has_final": decision.final_answer is not None,
                        "usage": ledger.usage.model_dump(),
                    },
                )
                pending_results = []

                if decision.tool_calls:
                    if state.status == TaskStatus.PLANNING:
                        state.transition(TaskStatus.ACTING)
                    for call in decision.tool_calls:
                        if call.name == "run_tests" and state.status != TaskStatus.VERIFYING:
                            state.transition(TaskStatus.VERIFYING)
                        result = dispatcher.dispatch(call)
                        pending_results.append(result)
                        if result.metadata.get("mutated"):
                            mutation_generation += 1
                        if call.name == "run_tests" and result.ok:
                            latest_tests = parse_dispatch_result(result)
                            failure_output = result.output if not latest_tests.successful else ""
                            if latest_tests.successful:
                                verified_generation = mutation_generation
                    if state.status in {TaskStatus.ACTING, TaskStatus.VERIFYING}:
                        state.transition(TaskStatus.PLANNING)
                    next_prompt = continuation_prompt(
                        ledger.usage,
                        "Tests are still failing; use the failure evidence."
                        if failure_output
                        else "Inspect the results and continue toward verified completion.",
                    )
                    continue

                if decision.final_answer is not None:
                    final_summary = decision.final_answer
                    if verified_generation != mutation_generation:
                        state.transition(TaskStatus.VERIFYING)
                        verification_call = ToolCall(
                            id=f"verify-{mutation_generation}",
                            name="run_tests",
                            arguments=RunTestsArgs().model_dump(),
                        )
                        result = dispatcher.dispatch(verification_call)
                        if result.ok:
                            latest_tests = parse_dispatch_result(result)
                            if latest_tests.successful:
                                verified_generation = mutation_generation
                                state.transition(TaskStatus.SUCCEEDED)
                                break
                            failure_output = result.output
                        else:
                            failure_output = result.error or "test tool failed"
                        pending_results = [result]
                        state.transition(TaskStatus.PLANNING)
                        refreshed_context = selector.select(
                            issue.prompt,
                            token_budget=self.config.context_token_budget,
                            failure_output=failure_output,
                        )
                        next_prompt = continuation_prompt(
                            ledger.usage,
                            "Automatic verification failed. Diagnose the output and fix the "
                            "implementation.\n"
                            + failure_output[-4_000:]
                            + "\nRelevant refreshed context:\n"
                            + refreshed_context.render(),
                        )
                        continue
                    state.transition(TaskStatus.VERIFYING)
                    state.transition(TaskStatus.SUCCEEDED)
                    break

                state.transition(TaskStatus.FAILED)
                final_summary = "Model returned neither a tool call nor a final answer."

        except BudgetExceeded as error:
            if not state.terminal:
                state.transition(TaskStatus.BUDGET_EXHAUSTED)
            final_summary = str(error)
            journal.append(
                "budget.exhausted",
                {"dimension": error.dimension, "message": str(error)},
            )
        except Exception as error:  # The event journal preserves unexpected runtime failures.
            if not state.terminal:
                state.transition(TaskStatus.FAILED)
            final_summary = f"{type(error).__name__}: {error}"
            journal.append("run.error", {"type": type(error).__name__, "message": str(error)})

        patch = git_output(self.config.repository, ["git", "diff", "--no-ext-diff"])
        changed = git_output(
            self.config.repository,
            ["git", "diff", "--name-only", "--no-ext-diff"],
        ).splitlines()
        result = RunResult(
            run_id=run_id,
            status=state.status,
            issue=issue,
            usage=ledger.usage,
            summary=final_summary,
            changed_files=changed,
            test_report=latest_tests,
            patch=patch,
            events_path=str(journal.path),
            started_at=started,
            finished_at=datetime.now(UTC),
        )
        journal.append("run.finished", result.model_dump(mode="json"))
        return result


def parse_dispatch_result(result: ToolResult) -> TestReport:
    from forgemcp.agent.verification import parse_test_observation
    from forgemcp.tools.toolset import RawObservation

    return parse_test_observation(RawObservation(result.output, result.metadata))


def git_output(root: Path, command: list[str]) -> str:
    try:
        process = subprocess.run(
            command,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return process.stdout.rstrip()


def config_for_log(config: RunConfig) -> dict[str, object]:
    return {
        "repository": str(config.repository),
        "model": config.model,
        "context_token_budget": config.context_token_budget,
        "budget": config.budget.model_dump(),
        "approval_mode": config.approval_mode,
        "test_command": config.test_command,
        "execution_mode": config.execution_mode,
        "docker_image": config.docker_image,
        "cpu_limit": config.cpu_limit,
        "memory_mb": config.memory_mb,
        "pids_limit": config.pids_limit,
        "allow_network": config.allow_network,
    }
