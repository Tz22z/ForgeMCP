"""Tree-sitter symbol extraction with a Python AST fallback."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any, Iterable

from forgemcp.context.files import SourceFile


@dataclass(frozen=True, slots=True)
class Symbol:
    path: str
    name: str
    qualified_name: str
    kind: str
    start_line: int
    end_line: int
    signature: str


@dataclass(frozen=True, slots=True)
class ImportRef:
    path: str
    module: str
    name: str | None
    line: int


@dataclass(frozen=True, slots=True)
class ParsedFile:
    symbols: tuple[Symbol, ...]
    imports: tuple[ImportRef, ...]
    parser: str


_NODE_KINDS: dict[str, dict[str, str]] = {
    "python": {
        "function_definition": "function",
        "class_definition": "class",
    },
    "javascript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
    },
    "typescript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "interface_declaration": "interface",
        "method_definition": "method",
    },
    "tsx": {
        "function_declaration": "function",
        "class_declaration": "class",
        "interface_declaration": "interface",
        "method_definition": "method",
    },
    "go": {
        "function_declaration": "function",
        "method_declaration": "method",
        "type_declaration": "type",
    },
    "rust": {
        "function_item": "function",
        "struct_item": "struct",
        "enum_item": "enum",
        "trait_item": "trait",
    },
    "java": {
        "method_declaration": "method",
        "class_declaration": "class",
        "interface_declaration": "interface",
    },
}


class SymbolExtractor:
    def __init__(self, *, prefer_tree_sitter: bool = True) -> None:
        self.prefer_tree_sitter = prefer_tree_sitter

    def parse(self, source: SourceFile) -> ParsedFile:
        if self.prefer_tree_sitter and source.language in _NODE_KINDS:
            parsed = self._tree_sitter(source)
            if parsed is not None:
                return parsed
        if source.language == "python":
            return self._python_ast(source)
        return ParsedFile((), tuple(self._regex_imports(source)), "text")

    def _tree_sitter(self, source: SourceFile) -> ParsedFile | None:
        try:
            from tree_sitter_language_pack import get_parser

            parser = get_parser(source.language)
            tree = parser.parse(source.text.encode())
        except (ImportError, LookupError, RuntimeError):
            return None

        symbols: list[Symbol] = []
        kinds = _NODE_KINDS[source.language]
        for node in self._walk(tree.root_node):
            kind = kinds.get(node.type)
            if kind is None:
                continue
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = source.text.encode()[name_node.start_byte : name_node.end_byte].decode()
            signature = source.text.encode()[node.start_byte : node.end_byte].decode().splitlines()[0]
            symbols.append(
                Symbol(
                    path=source.relative_path,
                    name=name,
                    qualified_name=name,
                    kind=kind,
                    start_line=node.start_point.row + 1,
                    end_line=node.end_point.row + 1,
                    signature=signature[:500],
                )
            )
        return ParsedFile(tuple(symbols), tuple(self._regex_imports(source)), "tree-sitter")

    def _python_ast(self, source: SourceFile) -> ParsedFile:
        try:
            tree = ast.parse(source.text, filename=source.relative_path)
        except SyntaxError:
            return ParsedFile((), tuple(self._regex_imports(source)), "python-ast-error")

        symbols: list[Symbol] = []
        imports: list[ImportRef] = []

        def visit(body: Iterable[ast.stmt], parents: tuple[str, ...] = ()) -> None:
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    kind = "class" if isinstance(node, ast.ClassDef) else "function"
                    if parents and kind == "function":
                        kind = "method"
                    qualified = ".".join((*parents, node.name))
                    line = ast.get_source_segment(source.text, node)
                    signature = (line or node.name).splitlines()[0]
                    symbols.append(
                        Symbol(
                            path=source.relative_path,
                            name=node.name,
                            qualified_name=qualified,
                            kind=kind,
                            start_line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                            signature=signature[:500],
                        )
                    )
                    visit(node.body, (*parents, node.name))
                elif isinstance(node, ast.Import):
                    imports.extend(
                        ImportRef(source.relative_path, alias.name, alias.asname, node.lineno)
                        for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom):
                    module = "." * node.level + (node.module or "")
                    imports.extend(
                        ImportRef(source.relative_path, module, alias.name, node.lineno)
                        for alias in node.names
                    )

        visit(tree.body)
        return ParsedFile(tuple(symbols), tuple(imports), "python-ast")

    @staticmethod
    def _walk(root: Any) -> Iterable[Any]:
        stack = [root]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    @staticmethod
    def _regex_imports(source: SourceFile) -> Iterable[ImportRef]:
        patterns = (
            re.compile(r"^\s*(?:from\s+([\w.]+)\s+)?import\s+([\w.]+)"),
            re.compile(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]"),
            re.compile(r"^\s*(?:const|let|var).*?require\(['\"]([^'\"]+)['\"]\)"),
        )
        for line_number, line in enumerate(source.text.splitlines(), start=1):
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    groups = [group for group in match.groups() if group]
                    if groups:
                        yield ImportRef(source.relative_path, groups[0], None, line_number)
                    break

