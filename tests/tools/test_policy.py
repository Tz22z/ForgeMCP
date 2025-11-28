from pathlib import Path

import pytest

from forgemcp.core.models import RiskLevel
from forgemcp.tools.policy import ApprovalRequired, PolicyViolation, ToolPolicy


def test_policy_confines_reads_to_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "secret.txt").write_text("secret")
    policy = ToolPolicy(repo)
    with pytest.raises(PolicyViolation, match="escapes repository"):
        policy.resolve_read("../secret.txt")


def test_policy_denies_git_metadata_write(tmp_path: Path) -> None:
    policy = ToolPolicy(tmp_path)
    with pytest.raises(PolicyViolation, match="protected path"):
        policy.resolve_write(".git/config", 5)


def test_policy_rejects_absolute_paths(tmp_path: Path) -> None:
    policy = ToolPolicy(tmp_path)
    with pytest.raises(PolicyViolation, match="absolute paths"):
        policy.resolve_write(str(tmp_path / "file.py"), 1)


def test_high_risk_tool_requires_approval(tmp_path: Path) -> None:
    policy = ToolPolicy(tmp_path, approval_mode="on-risk")
    with pytest.raises(ApprovalRequired):
        policy.authorize("delete_file", RiskLevel.HIGH)


def test_explicit_tool_approval_is_narrow(tmp_path: Path) -> None:
    policy = ToolPolicy(tmp_path, approved_tools=frozenset({"delete_file"}))
    policy.authorize("delete_file", RiskLevel.HIGH)
