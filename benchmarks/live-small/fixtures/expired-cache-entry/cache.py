from dataclasses import dataclass


@dataclass(frozen=True)
class CacheEntry:
    value: object
    expires_at: int


class ExpiringCache:
    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}

    def put(self, key: str, value: object, *, expires_at: int) -> None:
        self._entries[key] = CacheEntry(value=value, expires_at=expires_at)

    def get(self, key: str, *, now: int) -> object | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            return entry.value
        return entry.value
