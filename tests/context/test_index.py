from pathlib import Path

from forgemcp.context.index import RepositoryIndex
from forgemcp.context.symbols import SymbolExtractor


def make_index(root: Path) -> RepositoryIndex:
    return RepositoryIndex(
        root,
        database=root / ".forgemcp" / "test.sqlite3",
        extractor=SymbolExtractor(prefer_tree_sitter=False),
    )


def test_refresh_only_reparses_changed_files(tmp_path: Path) -> None:
    (tmp_path / "one.py").write_text("def one():\n    return 1\n")
    index = make_index(tmp_path)

    first = index.refresh()
    second = index.refresh()

    assert first.parsed == 1
    assert first.symbols == 1
    assert second.parsed == 0
    assert second.unchanged == 1


def test_refresh_removes_deleted_files(tmp_path: Path) -> None:
    target = tmp_path / "gone.py"
    target.write_text("x = 1")
    index = make_index(tmp_path)
    index.refresh()
    target.unlink()

    stats = index.refresh()

    assert stats.removed == 1
    assert index.files() == []


def test_dependency_lookup_and_invalidation(tmp_path: Path) -> None:
    (tmp_path / "cache.py").write_text("class Cache:\n    pass\n")
    (tmp_path / "service.py").write_text("from cache import Cache\n")
    index = make_index(tmp_path)
    index.refresh()

    assert index.dependent_paths("cache.py") == ["service.py"]
    assert index.invalidate("cache.py") == ["service.py"]
    assert [row["path"] for row in index.files()] == ["service.py"]


def test_read_metrics_reset_when_content_changes(tmp_path: Path) -> None:
    index = make_index(tmp_path)
    assert index.record_read("a.py", "v1") is False
    assert index.record_read("a.py", "v1") is True
    assert index.record_read("a.py", "v2") is False
    assert index.read_metrics()["repeated_read_ratio"] == 0.0
