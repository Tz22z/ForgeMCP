"""Hybrid repository context selection under a fixed token budget."""

from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from forgemcp.context.index import RepositoryIndex
from forgemcp.core.models import ContextBundle, ContextSnippet

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_LOCATION = re.compile(r"(?P<path>[\w./-]+\.(?:py|js|ts|tsx|go|rs|java)):(?P<line>\d+)")
_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "when",
    "into",
    "should",
    "test",
    "tests",
    "fix",
    "issue",
}


@dataclass(slots=True)
class Candidate:
    path: str
    score: float = 0.0
    reasons: set[str] = field(default_factory=set)
    focus_lines: list[int] = field(default_factory=list)

    def add(self, points: float, reason: str, line: int | None = None) -> None:
        self.score += points
        self.reasons.add(reason)
        if line is not None:
            self.focus_lines.append(line)


class ContextSelector:
    """Rank lexical, symbolic, dependency, diff, and failure-location signals."""

    def __init__(self, index: RepositoryIndex) -> None:
        self.index = index
        self.root = index.root

    def select(
        self,
        query: str,
        *,
        token_budget: int,
        failure_output: str = "",
        recent_diff: set[str] | None = None,
    ) -> ContextBundle:
        terms = self._terms(query)
        candidates: dict[str, Candidate] = {
            row["path"]: Candidate(row["path"]) for row in self.index.files()
        }
        recent = recent_diff if recent_diff is not None else self._recent_diff_paths()

        for path, candidate in candidates.items():
            lowered = path.lower()
            matches = [term for term in terms if term in lowered]
            if matches:
                candidate.add(3.0 + len(matches), "path-match")
            if path in recent:
                candidate.add(2.5, "recent-diff")

        for term in terms:
            for symbol in self.index.symbols(term, limit=50):
                candidate = candidates.get(symbol["path"])
                if candidate is None:
                    continue
                exact = symbol["name"].lower() == term
                candidate.add(7.0 if exact else 4.0, "symbol-match", symbol["start_line"])
                for dependent in self.index.dependent_paths(symbol["path"]):
                    if dependent in candidates:
                        candidates[dependent].add(1.75, "symbol-dependent")

        for match in _LOCATION.finditer(failure_output):
            path = match.group("path").removeprefix("./")
            if path in candidates:
                candidates[path].add(12.0, "failure-location", int(match.group("line")))

        self._add_test_pairs(candidates)
        ranked = sorted(candidates.values(), key=lambda item: (-item.score, item.path))
        snippets: list[ContextSnippet] = []
        used = 0
        for candidate in ranked:
            if candidate.score <= 0:
                continue
            source = self.index.scanner.read(candidate.path)
            if source is None:
                continue
            start, end, text = self._slice(source.text, candidate.focus_lines)
            estimate = self.estimate_tokens(text)
            if estimate > token_budget - used:
                remaining = token_budget - used
                if remaining < 80:
                    continue
                text = self._truncate_to_tokens(text, remaining)
                end = start + text.count("\n")
                estimate = self.estimate_tokens(text)
            snippets.append(
                ContextSnippet(
                    path=candidate.path,
                    start_line=start,
                    end_line=max(start, end),
                    text=text,
                    score=round(candidate.score, 3),
                    reasons=sorted(candidate.reasons),
                    estimated_tokens=estimate,
                )
            )
            self.index.record_read(candidate.path, source.content_hash)
            used += estimate
            if used >= token_budget:
                break

        return ContextBundle(
            query=query,
            snippets=snippets,
            estimated_tokens=used,
            omitted_candidates=max(0, sum(item.score > 0 for item in ranked) - len(snippets)),
            strategy="hybrid-symbol-dependency-diff-failure",
        )

    def _add_test_pairs(self, candidates: dict[str, Candidate]) -> None:
        scored = [item for item in candidates.values() if item.score > 0]
        for candidate in scored:
            source = Path(candidate.path)
            stem = source.stem.removeprefix("test_")
            possible = {
                f"tests/test_{stem}.py",
                f"test_{stem}.py",
                str(source.with_name(f"test_{stem}.py")),
            }
            for paired in possible:
                if paired in candidates and paired != candidate.path:
                    candidates[paired].add(2.25, "test-pair")

    def _recent_diff_paths(self) -> set[str]:
        try:
            process = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~5", "HEAD"],
                cwd=self.root,
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired):
            return set()
        if process.returncode != 0:
            return set()
        return {line.strip() for line in process.stdout.splitlines() if line.strip()}

    @staticmethod
    def _terms(query: str) -> set[str]:
        terms: set[str] = set()
        for word in _WORD.findall(query):
            lowered = word.lower()
            if lowered not in _STOPWORDS:
                terms.add(lowered)
            for part in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", word):
                part = part.lower()
                if len(part) >= 3 and part not in _STOPWORDS:
                    terms.add(part)
        return terms

    @staticmethod
    def _slice(text: str, focus_lines: list[int], radius: int = 35) -> tuple[int, int, str]:
        lines = text.splitlines()
        if not lines:
            return 1, 1, ""
        if len(lines) <= radius * 2 or not focus_lines:
            return 1, len(lines), text
        focus = min(focus_lines)
        start = max(1, focus - radius)
        end = min(len(lines), focus + radius)
        return start, end, "\n".join(lines[start - 1 : end])

    @staticmethod
    def estimate_tokens(text: str) -> int:
        # A conservative provider-independent estimate suitable for hard context packing.
        return max(1, (len(text.encode("utf-8")) + 2) // 3)

    @staticmethod
    def _truncate_to_tokens(text: str, tokens: int) -> str:
        byte_budget = max(0, tokens * 3)
        return text.encode("utf-8")[:byte_budget].decode("utf-8", errors="ignore")

