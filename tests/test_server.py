from pathlib import Path

import pytest

from forgemcp.server import resolve_repository


def test_server_repository_is_confined(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "root"
    child = root / "project"
    child.mkdir(parents=True)
    monkeypatch.setenv("FORGEMCP_ROOT", str(root))
    assert resolve_repository("project") == child
    with pytest.raises(ValueError, match="escapes"):
        resolve_repository("../outside")


def test_server_rejects_absolute_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FORGEMCP_ROOT", str(tmp_path))
    with pytest.raises(ValueError, match="relative"):
        resolve_repository(str(tmp_path))
