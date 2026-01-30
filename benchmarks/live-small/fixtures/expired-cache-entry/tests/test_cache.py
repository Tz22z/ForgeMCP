from cache import ExpiringCache


def test_missing_entry_returns_none() -> None:
    assert ExpiringCache().get("missing", now=10) is None


def test_fresh_entry_is_returned() -> None:
    cache = ExpiringCache()
    cache.put("session", "active", expires_at=11)
    assert cache.get("session", now=10) == "active"
