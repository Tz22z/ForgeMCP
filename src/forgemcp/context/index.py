"""Persistent incremental index over files, symbols, and imports."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forgemcp.context.files import RepositoryScanner, SourceFile
from forgemcp.context.symbols import ParsedFile, SymbolExtractor


@dataclass(frozen=True, slots=True)
class IndexStats:
    discovered: int
    parsed: int
    unchanged: int
    removed: int
    symbols: int


class RepositoryIndex:
    """SQLite-backed index that reparses only changed files."""

    def __init__(
        self,
        root: Path,
        database: Path | None = None,
        *,
        scanner: RepositoryScanner | None = None,
        extractor: SymbolExtractor | None = None,
    ) -> None:
        self.root = root.resolve()
        self.database = database or self.root / ".forgemcp" / "index.sqlite3"
        self.scanner = scanner or RepositoryScanner(self.root)
        self.extractor = extractor or SymbolExtractor(
            cache_dir=self.database.parent / "tree-sitter"
        )
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    language TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    modified_ns INTEGER NOT NULL,
                    line_count INTEGER NOT NULL,
                    parser TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY,
                    path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    qualified_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    signature TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS symbols_name_idx ON symbols(name);
                CREATE INDEX IF NOT EXISTS symbols_path_idx ON symbols(path);
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY,
                    path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
                    module TEXT NOT NULL,
                    imported_name TEXT,
                    line INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS imports_path_idx ON imports(path);
                CREATE INDEX IF NOT EXISTS imports_module_idx ON imports(module);
                CREATE TABLE IF NOT EXISTS file_reads (
                    path TEXT PRIMARY KEY,
                    reads INTEGER NOT NULL DEFAULT 0,
                    last_hash TEXT NOT NULL
                );
                """
            )

    def refresh(self) -> IndexStats:
        sources = list(self.scanner.scan())
        discovered = {source.relative_path for source in sources}
        parsed_count = unchanged = symbol_count = 0
        with self.connect() as connection:
            existing = {
                row["path"]: row["content_hash"]
                for row in connection.execute("SELECT path, content_hash FROM files")
            }
            for source in sources:
                if existing.get(source.relative_path) == source.content_hash:
                    unchanged += 1
                    continue
                parsed = self.extractor.parse(source)
                self._replace_file(connection, source, parsed)
                parsed_count += 1
                symbol_count += len(parsed.symbols)

            removed_paths = set(existing) - discovered
            if removed_paths:
                connection.executemany(
                    "DELETE FROM files WHERE path = ?",
                    ((path,) for path in removed_paths),
                )
                connection.executemany(
                    "DELETE FROM file_reads WHERE path = ?", ((p,) for p in removed_paths)
                )

        return IndexStats(
            discovered=len(sources),
            parsed=parsed_count,
            unchanged=unchanged,
            removed=len(removed_paths),
            symbols=symbol_count,
        )

    @staticmethod
    def _replace_file(
        connection: sqlite3.Connection,
        source: SourceFile,
        parsed: ParsedFile,
    ) -> None:
        connection.execute("DELETE FROM files WHERE path = ?", (source.relative_path,))
        connection.execute(
            """INSERT INTO files
               (path, language, content_hash, size_bytes, modified_ns, line_count, parser)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                source.relative_path,
                source.language,
                source.content_hash,
                source.size_bytes,
                source.modified_ns,
                source.line_count,
                parsed.parser,
            ),
        )
        connection.executemany(
            """INSERT INTO symbols
               (path, name, qualified_name, kind, start_line, end_line, signature)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                (
                    item.path,
                    item.name,
                    item.qualified_name,
                    item.kind,
                    item.start_line,
                    item.end_line,
                    item.signature,
                )
                for item in parsed.symbols
            ),
        )
        connection.executemany(
            "INSERT INTO imports (path, module, imported_name, line) VALUES (?, ?, ?, ?)",
            ((item.path, item.module, item.name, item.line) for item in parsed.imports),
        )

    def invalidate(self, relative_path: str) -> list[str]:
        """Drop stale data and return files that may depend on the changed path."""
        module = self._module_name(relative_path)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT path FROM imports WHERE module = ? OR module LIKE ?",
                (module, f"%{module}"),
            ).fetchall()
            connection.execute("DELETE FROM files WHERE path = ?", (relative_path,))
        return sorted(row["path"] for row in rows if row["path"] != relative_path)

    def files(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM files ORDER BY path").fetchall()
        return [dict(row) for row in rows]

    def symbols(self, query: str = "", limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if query:
                needle = f"%{query}%"
                rows = connection.execute(
                    """SELECT * FROM symbols
                       WHERE name LIKE ? OR qualified_name LIKE ? OR signature LIKE ?
                       ORDER BY CASE WHEN name = ? THEN 0 ELSE 1 END, path, start_line
                       LIMIT ?""",
                    (needle, needle, needle, query, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM symbols ORDER BY path, start_line LIMIT ?", (limit,)
                ).fetchall()
        return [dict(row) for row in rows]

    def imports_for(self, path: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM imports WHERE path = ? ORDER BY line", (path,)
            ).fetchall()
        return [dict(row) for row in rows]

    def dependent_paths(self, path: str) -> list[str]:
        module = self._module_name(path)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT path FROM imports WHERE module = ? OR module LIKE ? ORDER BY path",
                (module, f"%{module}"),
            ).fetchall()
        return [row["path"] for row in rows if row["path"] != path]

    def record_read(self, path: str, content_hash: str) -> bool:
        """Record a file read; return True when the same version was already read."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT reads, last_hash FROM file_reads WHERE path = ?", (path,)
            ).fetchone()
            repeated = row is not None and row["last_hash"] == content_hash
            connection.execute(
                """INSERT INTO file_reads(path, reads, last_hash) VALUES (?, 1, ?)
                   ON CONFLICT(path) DO UPDATE SET
                   reads = CASE WHEN last_hash = excluded.last_hash THEN reads + 1 ELSE 1 END,
                   last_hash = excluded.last_hash""",
                (path, content_hash),
            )
        return repeated

    def read_metrics(self) -> dict[str, int | float]:
        with self.connect() as connection:
            rows = connection.execute("SELECT reads FROM file_reads").fetchall()
        total = sum(row["reads"] for row in rows)
        repeats = sum(max(0, row["reads"] - 1) for row in rows)
        return {
            "file_reads": total,
            "repeated_file_reads": repeats,
            "repeated_read_ratio": round(repeats / total, 4) if total else 0.0,
        }

    @staticmethod
    def _module_name(path: str) -> str:
        without_suffix = path.rsplit(".", maxsplit=1)[0]
        parts = without_suffix.split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        while parts and parts[0] in {"src", "lib", "app"}:
            parts = parts[1:]
        return ".".join(parts)
