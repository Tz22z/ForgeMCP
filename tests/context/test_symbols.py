from pathlib import Path

from forgemcp.context.files import SourceFile
from forgemcp.context.symbols import SymbolExtractor


def source(text: str, language: str = "python") -> SourceFile:
    return SourceFile(
        path=Path("service.py"),
        relative_path="service.py",
        language=language,
        text=text,
        content_hash="hash",
        size_bytes=len(text),
        modified_ns=1,
    )


def test_python_ast_extracts_nested_symbols_and_imports() -> None:
    parsed = SymbolExtractor(prefer_tree_sitter=False).parse(
        source(
            "from app.cache import Cache\n\n"
            "class Service:\n"
            "    def get(self, key: str) -> str:\n"
            "        return key\n"
        )
    )
    assert [(item.qualified_name, item.kind) for item in parsed.symbols] == [
        ("Service", "class"),
        ("Service.get", "method"),
    ]
    assert parsed.imports[0].module == "app.cache"
    assert parsed.imports[0].name == "Cache"


def test_invalid_python_is_still_indexable() -> None:
    parsed = SymbolExtractor(prefer_tree_sitter=False).parse(source("def broken(:\n"))
    assert parsed.symbols == ()
    assert parsed.parser == "python-ast-error"


def test_regex_extracts_javascript_dependency() -> None:
    parsed = SymbolExtractor(prefer_tree_sitter=False).parse(
        source("import { cache } from './cache';\n", "javascript")
    )
    assert parsed.imports[0].module == "./cache"
