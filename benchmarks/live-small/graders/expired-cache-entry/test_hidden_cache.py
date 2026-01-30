from cache import ExpiringCache


def test_expired_entries_are_removed_at_and_after_boundary() -> None:
    cache = ExpiringCache()
    cache.put("at-boundary", "stale", expires_at=10)
    cache.put("past-boundary", "older", expires_at=9)

    assert cache.get("at-boundary", now=10) is None
    assert cache.get("past-boundary", now=10) is None
    assert "at-boundary" not in cache._entries
    assert "past-boundary" not in cache._entries
