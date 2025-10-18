from pathlib import Path

import pytest

from forgemcp.context.files import RepositoryScanner


def test_scan_discovers_text_and_skips_binary(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "app.py").write_text("def main():\n    return 1\n")
    (tmp_path / "image.bin").write_bytes(b"abc\x00def")

    files = list(RepositoryScanner(tmp_path).scan())

    assert [item.relative_path for item in files] == ["pkg/app.py"]
    assert files[0].language == "python"
    assert files[0].line_count == 2


def test_scan_skips_generated_directories(tmp_path: Path) -> None:
    cache = tmp_path / "pkg" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "module.py").write_text("cached = True")
    assert list(RepositoryScanner(tmp_path).scan()) == []


def test_read_rejects_path_traversal(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "secret.py"
    outside.write_text("SECRET = 1")
    with pytest.raises(ValueError, match="escapes repository"):
        RepositoryScanner(root).read("../secret.py")


def test_read_skips_oversized_file(tmp_path: Path) -> None:
    (tmp_path / "big.py").write_text("x" * 20)
    scanner = RepositoryScanner(tmp_path, max_file_bytes=10)
    assert scanner.read("big.py") is None

