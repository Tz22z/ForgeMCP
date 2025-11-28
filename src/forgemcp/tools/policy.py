"""Authorization and path confinement for every tool dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from forgemcp.core.models import RiskLevel


class PolicyViolation(PermissionError):
    pass


class ApprovalRequired(PermissionError):
    def __init__(self, tool_name: str, reason: str) -> None:
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"approval required for {tool_name}: {reason}")


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    repository: Path
    approval_mode: Literal["never", "on-risk", "always"] = "on-risk"
    approved_tools: frozenset[str] = field(default_factory=frozenset)
    denied_write_paths: tuple[str, ...] = (
        ".git",
        ".forgemcp",
        ".env",
        ".env.local",
    )
    max_write_bytes: int = 500_000
    max_read_bytes: int = 1_000_000

    @property
    def root(self) -> Path:
        return self.repository.resolve()

    def resolve_read(self, relative_path: str) -> Path:
        path = self._resolve(relative_path)
        if not path.is_file():
            raise PolicyViolation(f"not a regular file: {relative_path}")
        if path.stat().st_size > self.max_read_bytes:
            raise PolicyViolation(f"file exceeds {self.max_read_bytes} byte read limit")
        return path

    def resolve_write(self, relative_path: str, content_size: int = 0) -> Path:
        path = self._resolve(relative_path)
        normalized = path.relative_to(self.root).as_posix()
        if any(
            normalized == item or normalized.startswith(f"{item}/")
            for item in self.denied_write_paths
        ):
            raise PolicyViolation(f"writes denied for protected path: {normalized}")
        if path.exists() and path.is_symlink():
            raise PolicyViolation(f"refusing to write through symlink: {relative_path}")
        if content_size > self.max_write_bytes:
            raise PolicyViolation(f"write exceeds {self.max_write_bytes} byte limit")
        return path

    def authorize(self, tool_name: str, risk: RiskLevel, reason: str = "") -> None:
        if tool_name in self.approved_tools:
            return
        requires_approval = self.approval_mode == "always" or (
            self.approval_mode == "on-risk" and risk == RiskLevel.HIGH
        )
        if requires_approval:
            raise ApprovalRequired(tool_name, reason or f"{risk.value}-risk operation")

    def _resolve(self, relative_path: str) -> Path:
        if not relative_path or relative_path == ".":
            raise PolicyViolation("a repository-relative file path is required")
        supplied = Path(relative_path)
        if supplied.is_absolute():
            raise PolicyViolation("absolute paths are not allowed")
        path = (self.root / supplied).resolve(strict=False)
        if not path.is_relative_to(self.root):
            raise PolicyViolation(f"path escapes repository: {relative_path}")
        return path
