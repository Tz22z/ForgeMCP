# Security model

ForgeMCP assumes issue text, repository contents, and model output are untrusted.
The runtime uses several independent controls rather than treating prompting as a
security boundary.

## Boundaries

- Tool arguments are validated against strict schemas before dispatch.
- File paths must be relative and resolve beneath the configured repository.
- Writes to `.git`, `.forgemcp`, and environment files are denied.
- Test targets cannot inject flags, and only a small test-flag allowlist is accepted.
- Commands are passed as argument vectors without a shell.
- Tool output is bounded; full output is written to an internal observation reference.
- High-risk tools require explicit approval under the default policy.
- Docker execution drops all Linux capabilities, blocks privilege escalation, uses a
  read-only root filesystem, caps CPU, memory, and process count, and disables network
  access by default.

Docker isolation does not make arbitrary third-party code risk-free. Use a disposable
host or stronger VM boundary when evaluating unknown repositories with kernel-level
threats in scope.

## Reporting a vulnerability

Please open a private GitHub security advisory with reproduction steps, affected
versions, and impact. Do not include secrets from a real run journal.

