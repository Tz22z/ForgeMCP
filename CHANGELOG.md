# Changelog

All notable changes to ForgeMCP are documented here.

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

- 56 automated tests.
- 80% measured line coverage in the reconstruction environment.
- Wheel and source distribution build successfully.
- Hardened Docker image builds and loads pre-fetched Tree-sitter parsers with network
  disabled and a read-only root filesystem.
