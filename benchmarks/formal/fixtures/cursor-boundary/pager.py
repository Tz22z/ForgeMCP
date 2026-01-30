from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Page:
    items: list[T]
    next_cursor: int | None


def paginate(items: list[T], *, cursor: int = 0, page_size: int = 2) -> Page:
    if cursor < 0:
        raise ValueError("cursor must be non-negative")
    if page_size < 1:
        raise ValueError("page_size must be positive")
    batch = items[cursor : cursor + page_size]
    next_cursor = cursor + page_size if cursor + page_size <= len(items) else None
    return Page(items=batch, next_cursor=next_cursor)
