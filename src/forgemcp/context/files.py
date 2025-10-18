"""Safe, deterministic repository discovery."""

from __future__ import annotations

import fnmatch
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

DEFAULT_EXCLUDES = (
    ".git/**",
    ".venv/**",
    ".forgemcp/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ruff_cache/**",
    "**/node_modules/**",
    "**/dist/**",
    "**/build/**",
    "*.lock",
    "*.min.js",
    "*.map",
)

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".md": "markdown",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: Path
    relative_path: str
    language: str
    text: str
    content_hash: str
    size_bytes: int
    modified_ns: int

    @property
    def line_count(self) -> int:
        return self.text.count("\n") + bool(self.text)


class RepositoryScanner:
    """Walk source files without escaping the configured repository root."""

    def __init__(
        self,
        root: Path,
        *,
        excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
        max_file_bytes: int = 1_000_000,
    ) -> None:
        self.root = root.resolve()
        self.excludes = excludes
        self.max_file_bytes = max_file_bytes

    def scan(self) -> Iterator[SourceFile]:
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(self.root).as_posix()
            if self._excluded(relative):
                continue
            source = self.read(relative)
            if source is not None:
                yield source

    def read(self, relative_path: str) -> SourceFile | None:
        path = self._resolve(relative_path)
        stat = path.stat()
        if stat.st_size > self.max_file_bytes:
            return None
        raw = path.read_bytes()
        if b"\x00" in raw[:8192]:
            return None
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
        return SourceFile(
            path=path,
            relative_path=relative_path,
            language=LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "text"),
            text=text,
            content_hash=hashlib.sha256(raw).hexdigest(),
            size_bytes=stat.st_size,
            modified_ns=stat.st_mtime_ns,
        )

    def _resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"path escapes repository: {relative_path}")
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        return path

    def _excluded(self, relative: str) -> bool:
        parts = relative.split("/")
        candidates = {relative, f"**/{relative}"}
        candidates.update(parts)
        for pattern in self.excludes:
            if any(fnmatch.fnmatch(candidate, pattern) for candidate in candidates):
                return True
        return False

