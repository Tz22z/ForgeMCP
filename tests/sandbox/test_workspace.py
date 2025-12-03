import subprocess
from pathlib import Path

from forgemcp.sandbox.workspace import GitWorktreeManager


def git(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True, capture_output=True)


def test_workspace_lease_is_detached_and_removed(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    leases = tmp_path / "leases"
    repository.mkdir()
    leases.mkdir()
    git(["git", "init", "-q"], repository)
    (repository / "app.py").write_text("VALUE = 1\n")
    git(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", "."], repository
    )
    git(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "initial",
        ],
        repository,
    )
    manager = GitWorktreeManager(repository, leases)
    with manager.create("issue/unsafe:id") as lease:
        leased_path = lease.path
        assert (leased_path / "app.py").read_text() == "VALUE = 1\n"
        (leased_path / "app.py").write_text("VALUE = 2\n")
        assert (repository / "app.py").read_text() == "VALUE = 1\n"
    assert not leased_path.exists()
