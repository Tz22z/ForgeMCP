"""Shell-free local and Docker command runners."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: list[str]
    stdout: str
    stderr: str
    exit_code: int
    elapsed_seconds: float

    @property
    def output(self) -> str:
        if self.stdout and self.stderr:
            return f"{self.stdout.rstrip()}\n{self.stderr.rstrip()}"
        return (self.stdout or self.stderr).rstrip()


class CommandRunner(Protocol):
    def run(self, command: list[str], cwd: Path, timeout: int) -> CommandResult: ...


class LocalCommandRunner:
    """Execute an argument vector with a minimal environment and no shell."""

    def run(self, command: list[str], cwd: Path, timeout: int) -> CommandResult:
        started = time.monotonic()
        try:
            process = subprocess.run(
                command,
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={
                    "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                    "PYTHONPATH": str(cwd),
                    "LANG": "C.UTF-8",
                },
            )
        except subprocess.TimeoutExpired as error:
            stdout = (
                error.stdout.decode(errors="replace")
                if isinstance(error.stdout, bytes)
                else error.stdout
            )
            stderr = (
                error.stderr.decode(errors="replace")
                if isinstance(error.stderr, bytes)
                else error.stderr
            )
            raise TimeoutError(
                f"command timed out after {timeout}s\n{(stdout or '')}{(stderr or '')}"
            ) from error
        return CommandResult(
            command=command,
            stdout=process.stdout,
            stderr=process.stderr,
            exit_code=process.returncode,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )


class DockerCommandRunner:
    """Run tools in an unprivileged, resource-capped, network-isolated container."""

    def __init__(
        self,
        image: str = "forgemcp:latest",
        *,
        cpus: float = 2.0,
        memory_mb: int = 2_048,
        pids_limit: int = 256,
        allow_network: bool = False,
        delegate: CommandRunner | None = None,
    ) -> None:
        self.image = image
        self.cpus = cpus
        self.memory_mb = memory_mb
        self.pids_limit = pids_limit
        self.allow_network = allow_network
        self.delegate = delegate or LocalCommandRunner()

    def docker_command(self, command: list[str], cwd: Path) -> list[str]:
        network = "bridge" if self.allow_network else "none"
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            network,
            "--cpus",
            str(self.cpus),
            "--memory",
            f"{self.memory_mb}m",
            "--pids-limit",
            str(self.pids_limit),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=128m",
            "--volume",
            f"{cwd.resolve()}:/workspace:rw",
            "--workdir",
            "/workspace",
            "--entrypoint",
            "",
            self.image,
            *command,
        ]

    def run(self, command: list[str], cwd: Path, timeout: int) -> CommandResult:
        docker = self.docker_command(command, cwd)
        result = self.delegate.run(docker, cwd, timeout)
        return CommandResult(
            command=command,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            elapsed_seconds=result.elapsed_seconds,
        )
