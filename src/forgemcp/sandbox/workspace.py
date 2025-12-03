"""One detached Git worktree per task."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class WorkspaceLease:
    source: Path
    path: Path
    keep: bool = False

    def close(self) -> None:
        if self.keep or not self.path.exists():
            return
        process = subprocess.run(
            ["git", "worktree", "remove", "--force", str(self.path)],
            cwd=self.source,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if process.returncode != 0 and self.path.exists():
            shutil.rmtree(self.path)
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=self.source,
                check=False,
                capture_output=True,
                timeout=10,
            )

    def __enter__(self) -> WorkspaceLease:
        return self

    def __exit__(self, *_errors: object) -> None:
        self.close()


class GitWorktreeManager:
    def __init__(self, repository: Path, base_directory: Path | None = None) -> None:
        self.repository = repository.resolve()
        self.base_directory = base_directory

    def create(self, task_id: str, *, keep: bool = False) -> WorkspaceLease:
        prefix = f"forgemcp-{self._safe_id(task_id)}-"
        target = Path(tempfile.mkdtemp(prefix=prefix, dir=self.base_directory))
        # git worktree requires the target path not to exist.
        target.rmdir()
        process = subprocess.run(
            ["git", "worktree", "add", "--detach", str(target), "HEAD"],
            cwd=self.repository,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if process.returncode != 0:
            raise RuntimeError(f"failed to create isolated worktree: {process.stderr.strip()}")
        return WorkspaceLease(self.repository, target, keep)

    @staticmethod
    def _safe_id(task_id: str) -> str:
        safe = "".join(
            character for character in task_id if character.isalnum() or character in "-_"
        )
        return (safe or "task")[:40]
