from pathlib import Path

import pytest

from forgemcp.tools.policy import ToolPolicy
from forgemcp.tools.toolset import ReadFileArgs, ReplaceTextArgs, RepositoryTools, SearchArgs


def test_read_file_includes_stable_line_numbers(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("one\ntwo\nthree\n")
    result = RepositoryTools(ToolPolicy(tmp_path)).read_file(
        ReadFileArgs(path="a.py", start_line=2, end_line=3)
    )
    assert "    2 | two" in result.output
    assert "    3 | three" in result.output


def test_replace_text_is_atomic_on_count_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "a.py"
    path.write_text("x = 1\nx = 1\n")
    tools = RepositoryTools(ToolPolicy(tmp_path))
    with pytest.raises(ValueError, match="found 2"):
        tools.replace_text(ReplaceTextArgs(path="a.py", old="x = 1", new="x = 2"))
    assert path.read_text() == "x = 1\nx = 1\n"


def test_search_has_result_cap(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("needle\nneedle\nneedle\n")
    result = RepositoryTools(ToolPolicy(tmp_path)).search(SearchArgs(query="needle", max_results=2))
    assert result.metadata["count"] == 2
