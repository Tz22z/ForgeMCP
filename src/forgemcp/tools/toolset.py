"""Small, auditable file and repository tool implementations."""

from __future__ import annotations

import fnmatch
import hashlib
import re
import sys
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from forgemcp.core.models import RiskLevel
from forgemcp.sandbox.runners import CommandRunner, LocalCommandRunner
from forgemcp.tools.policy import PolicyViolation, ToolPolicy


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListFilesArgs(StrictArgs):
    pattern: str = "**/*"
    limit: int = Field(default=200, ge=1, le=2_000)


class ReadFileArgs(StrictArgs):
    path: str
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)


class SearchArgs(StrictArgs):
    query: str = Field(min_length=1, max_length=500)
    path: str = ""
    regex: bool = False
    max_results: int = Field(default=100, ge=1, le=500)


class ReplaceTextArgs(StrictArgs):
    path: str
    old: str = Field(min_length=1)
    new: str
    expected_replacements: int = Field(default=1, ge=1, le=100)


class WriteFileArgs(StrictArgs):
    path: str
    content: str
    overwrite: bool = False


class DeleteFileArgs(StrictArgs):
    path: str
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GitDiffArgs(StrictArgs):
    path: str | None = None
    staged: bool = False


class GitStatusArgs(StrictArgs):
    pass


class RunTestsArgs(StrictArgs):
    targets: list[str] = Field(default_factory=list, max_length=25)
    extra_args: list[str] = Field(default_factory=list, max_length=20)
    timeout_seconds: int = Field(default=120, ge=1, le=900)


@dataclass(frozen=True, slots=True)
class RawObservation:
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)


class RepositoryTools:
    def __init__(
        self,
        policy: ToolPolicy,
        test_command: list[str] | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        self.policy = policy
        self.root = policy.root
        self.test_command = test_command or [sys.executable, "-m", "pytest", "-q"]
        self.runner = runner or LocalCommandRunner()

    def list_files(self, args: ListFilesArgs) -> RawObservation:
        paths: list[str] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(self.root).as_posix()
            if relative.startswith((".git/", ".forgemcp/", ".venv/")):
                continue
            if fnmatch.fnmatch(relative, args.pattern):
                paths.append(relative)
            if len(paths) >= args.limit:
                break
        return RawObservation("\n".join(paths), {"count": len(paths)})

    def read_file(self, args: ReadFileArgs) -> RawObservation:
        path = self.policy.resolve_read(args.path)
        lines = path.read_text(encoding="utf-8").splitlines()
        end = min(args.end_line or len(lines), len(lines))
        if args.start_line > max(1, len(lines)):
            raise ValueError(f"start_line {args.start_line} exceeds {len(lines)} lines")
        selected = lines[args.start_line - 1 : end]
        numbered = "\n".join(
            f"{number:>5} | {line}" for number, line in enumerate(selected, args.start_line)
        )
        return RawObservation(
            numbered,
            {"path": args.path, "start_line": args.start_line, "end_line": end},
        )

    def search(self, args: SearchArgs) -> RawObservation:
        base = self.root
        if args.path:
            candidate = (self.root / args.path).resolve(strict=False)
            if not candidate.is_relative_to(self.root):
                raise PolicyViolation("search path escapes repository")
            base = candidate
        matcher = re.compile(args.query) if args.regex else None
        results: list[str] = []
        paths = [base] if base.is_file() else sorted(base.rglob("*"))
        for path in paths:
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(self.root).as_posix()
            if relative.startswith((".git/", ".forgemcp/", ".venv/")):
                continue
            try:
                safe_path = self.policy.resolve_read(relative)
                lines = safe_path.read_text(encoding="utf-8").splitlines()
            except (PolicyViolation, UnicodeDecodeError):
                continue
            for line_number, line in enumerate(lines, 1):
                matched = (
                    bool(matcher.search(line)) if matcher else args.query.lower() in line.lower()
                )
                if matched:
                    results.append(f"{relative}:{line_number}:{line[:500]}")
                    if len(results) >= args.max_results:
                        return RawObservation("\n".join(results), {"count": len(results)})
        return RawObservation("\n".join(results), {"count": len(results)})

    def replace_text(self, args: ReplaceTextArgs) -> RawObservation:
        path = self.policy.resolve_write(args.path, len(args.new.encode()))
        if not path.is_file():
            raise FileNotFoundError(args.path)
        current = path.read_text(encoding="utf-8")
        actual = current.count(args.old)
        if actual != args.expected_replacements:
            raise ValueError(
                f"expected {args.expected_replacements} occurrence(s), "
                f"found {actual}; file unchanged"
            )
        updated = current.replace(args.old, args.new)
        self.policy.resolve_write(args.path, len(updated.encode()))
        path.write_text(updated, encoding="utf-8")
        return RawObservation(
            f"replaced {actual} occurrence(s) in {args.path}",
            {"path": args.path, "replacements": actual, "mutated": True},
        )

    def write_file(self, args: WriteFileArgs) -> RawObservation:
        encoded = args.content.encode()
        path = self.policy.resolve_write(args.path, len(encoded))
        existed = path.exists()
        if existed and not args.overwrite:
            raise FileExistsError(f"{args.path} exists; set overwrite=true to replace it")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args.content, encoding="utf-8")
        action = "updated" if existed else "created"
        return RawObservation(
            f"{action} {args.path} ({len(encoded)} bytes)",
            {"path": args.path, "bytes": len(encoded), "mutated": True},
        )

    def delete_file(self, args: DeleteFileArgs) -> RawObservation:
        path = self.policy.resolve_write(args.path)
        if not path.is_file():
            raise FileNotFoundError(args.path)
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != args.expected_sha256:
            raise ValueError("file hash changed; refusing deletion")
        path.unlink()
        return RawObservation(
            f"deleted {args.path}",
            {"path": args.path, "mutated": True, "deleted": True},
        )

    def git_diff(self, args: GitDiffArgs) -> RawObservation:
        command = ["git", "diff"]
        if args.staged:
            command.append("--cached")
        command.extend(["--no-ext-diff", "--"])
        if args.path:
            self.policy._resolve(args.path)
            command.append(args.path)
        return self._run(command, timeout=15)

    def git_status(self, _args: GitStatusArgs) -> RawObservation:
        return self._run(["git", "status", "--short"], timeout=10)

    def run_tests(self, args: RunTestsArgs) -> RawObservation:
        for target in args.targets:
            if target.startswith("-"):
                raise PolicyViolation("test targets cannot be command flags")
            resolved = (self.root / target.split("::", 1)[0]).resolve(strict=False)
            if not resolved.is_relative_to(self.root):
                raise PolicyViolation(f"test target escapes repository: {target}")
        allowed_flags = {"-x", "--maxfail=1", "--tb=short", "-q", "-v", "-vv"}
        if any(item not in allowed_flags for item in args.extra_args):
            raise PolicyViolation("unsupported test argument")
        command = [*self.test_command, *args.extra_args, *args.targets]
        return self._run(command, timeout=args.timeout_seconds)

    def _run(self, command: list[str], timeout: int) -> RawObservation:
        result = self.runner.run(command, self.root, timeout)
        return RawObservation(
            result.output,
            {
                "command": result.command,
                "exit_code": result.exit_code,
                "elapsed_seconds": result.elapsed_seconds,
            },
        )


TOOL_SCHEMAS: dict[str, tuple[type[StrictArgs], RiskLevel, str]] = {
    "list_files": (ListFilesArgs, RiskLevel.LOW, "List repository files"),
    "read_file": (ReadFileArgs, RiskLevel.LOW, "Read a bounded line range"),
    "search": (SearchArgs, RiskLevel.LOW, "Search repository text"),
    "replace_text": (ReplaceTextArgs, RiskLevel.MEDIUM, "Replace an exact text occurrence"),
    "write_file": (WriteFileArgs, RiskLevel.MEDIUM, "Create or overwrite a repository file"),
    "delete_file": (DeleteFileArgs, RiskLevel.HIGH, "Delete an exact, content-hashed file"),
    "git_diff": (GitDiffArgs, RiskLevel.LOW, "Inspect the working tree diff"),
    "git_status": (GitStatusArgs, RiskLevel.LOW, "Inspect working tree status"),
    "run_tests": (RunTestsArgs, RiskLevel.LOW, "Run the configured test command"),
}
