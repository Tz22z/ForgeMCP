# Changelog

All notable changes to ForgeMCP are documented here.

## Unreleased

### Fixed

- Normalize Pydantic schemas for OpenAI strict function calling by requiring every
  declared property and forbidding additional properties.
- Keep runtime-generated verification results out of Responses API function-call
  history, preventing invalid synthetic call IDs on repair turns.
- Run evaluation pytest entry points in isolated mode so fixture files cannot shadow
  the test framework, and require a successful agent terminal state for a solve.

### Added

- Preserve agent summaries, pricing inputs, manifest hashes, and runtime environment
  metadata in evaluation reports.
- Add a four-case live integration benchmark with external graders and lexical
  distractors for baseline-versus-hybrid experiments.
- Extend the live evaluation to a formal eight-case, three-trial paired benchmark with
  six raw reports, external graders, input/report hashes, and an auditable summary.
- Add a generic paired-trial summarizer that verifies model, manifest, pricing, and case
  order before reporting solve rate, tool calls, tokens, repeated reads, and cost.

### Verification

- 63 automated tests, Ruff formatting/lint, and strict MyPy pass.
- Wheel and source distribution build successfully.
- Formal benchmark: 3 paired trials x 8 cases; both arms solve 17/24, while hybrid
  reduces average tool calls 17.3%, input tokens 25.8%, and cost per solve 22.0%.

## 0.1.0 — 2026-01-28

### Added

- Plan–act–verify runtime with explicit task states and hard call, token, time, and
  repetition budgets.
- OpenAI Responses API adapter with strict custom function tools.
- Incremental SQLite repository index with Tree-sitter symbols, import edges, content
  invalidation, recent-diff signals, and repeated-read metrics.
- Hybrid context selector and lexical full-file baseline for controlled ablations.
- Schema-validated file, Git, and test tools with path confinement and approval policy.
- Content-addressed deletion gated as a high-risk operation.
- Per-task Git worktree leasing and a Docker runner with network/resource restrictions.
- MCP 2.x server, Typer CLI, deterministic two-file repair demo, and hidden-grader
  evaluation harness.
- Strict MyPy, Ruff, Pytest, package-build, and container-build CI jobs.

### Verification

- 57 automated tests.
- 81% measured line coverage in the reconstruction environment.
- Wheel and source distribution build successfully.
- Hardened Docker image builds and loads pre-fetched Tree-sitter parsers with network
  disabled and a read-only root filesystem.
