"""Populate a Tree-sitter language-pack cache for offline container runs."""

from __future__ import annotations

import sys

from tree_sitter_language_pack import PackConfig, configure, get_parser

DEFAULT_LANGUAGES = ["python", "javascript", "typescript", "tsx", "go", "rust", "java"]


def main(cache_directory: str, languages: list[str]) -> None:
    configure(PackConfig(cache_dir=cache_directory))
    for language in languages:
        get_parser(language)
        print(f"cached {language}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: prefetch_parsers.py CACHE_DIR [LANGUAGE ...]")
    main(sys.argv[1], sys.argv[2:] or DEFAULT_LANGUAGES)
