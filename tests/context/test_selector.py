from pathlib import Path

from forgemcp.context.index import RepositoryIndex
from forgemcp.context.selector import ContextSelector
from forgemcp.context.symbols import SymbolExtractor


def indexed_repo(tmp_path: Path) -> RepositoryIndex:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "cache.py").write_text(
        "class ExpiringCache:\n    def get(self, key):\n        return None\n"
    )
    (tmp_path / "src" / "service.py").write_text("from cache import ExpiringCache\n")
    (tmp_path / "tests" / "test_cache.py").write_text("def test_expiry():\n    assert True\n")
    index = RepositoryIndex(
        tmp_path,
        database=tmp_path / ".forgemcp" / "test.sqlite3",
        extractor=SymbolExtractor(prefer_tree_sitter=False),
    )
    index.refresh()
    return index


def test_symbol_and_test_pair_rank_relevant_files(tmp_path: Path) -> None:
    selector = ContextSelector(indexed_repo(tmp_path))
    bundle = selector.select(
        "ExpiringCache returns stale values",
        token_budget=2_000,
        recent_diff=set(),
    )
    paths = [snippet.path for snippet in bundle.snippets]
    assert paths[0] == "src/cache.py"
    assert "tests/test_cache.py" in paths
    assert "symbol-match" in bundle.snippets[0].reasons


def test_failure_location_is_strongest_signal(tmp_path: Path) -> None:
    selector = ContextSelector(indexed_repo(tmp_path))
    bundle = selector.select(
        "unrelated failure",
        token_budget=2_000,
        failure_output="E   src/service.py:1: ValueError",
        recent_diff=set(),
    )
    assert bundle.snippets[0].path == "src/service.py"
    assert "failure-location" in bundle.snippets[0].reasons


def test_selector_never_crosses_token_budget(tmp_path: Path) -> None:
    selector = ContextSelector(indexed_repo(tmp_path))
    bundle = selector.select("cache service", token_budget=80, recent_diff=set())
    assert bundle.estimated_tokens <= 80


def test_repeated_selection_is_measured(tmp_path: Path) -> None:
    index = indexed_repo(tmp_path)
    selector = ContextSelector(index)
    selector.select("ExpiringCache", token_budget=2_000, recent_diff=set())
    selector.select("ExpiringCache", token_budget=2_000, recent_diff=set())
    assert index.read_metrics()["repeated_file_reads"] > 0
