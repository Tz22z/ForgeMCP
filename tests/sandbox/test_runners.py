from pathlib import Path

from forgemcp.sandbox.runners import CommandResult, DockerCommandRunner


class RecordingRunner:
    def __init__(self) -> None:
        self.command: list[str] = []

    def run(self, command: list[str], cwd: Path, timeout: int) -> CommandResult:
        self.command = command
        return CommandResult(command, "ok", "", 0, 0.1)


def test_docker_runner_applies_security_and_resource_limits(tmp_path: Path) -> None:
    recorder = RecordingRunner()
    runner = DockerCommandRunner(
        "forge:test",
        cpus=1.5,
        memory_mb=768,
        pids_limit=64,
        delegate=recorder,
    )
    result = runner.run(["python", "-m", "pytest"], tmp_path, 30)
    command = recorder.command
    assert result.output == "ok"
    assert "--network" in command and command[command.index("--network") + 1] == "none"
    assert "--cap-drop" in command and "ALL" in command
    assert "--read-only" in command
    assert command[command.index("--entrypoint") + 1] == ""
    assert "768m" in command
    assert command[-3:] == ["python", "-m", "pytest"]


def test_network_access_is_explicit_opt_in(tmp_path: Path) -> None:
    runner = DockerCommandRunner(allow_network=True)
    command = runner.docker_command(["true"], tmp_path)
    assert command[command.index("--network") + 1] == "bridge"
