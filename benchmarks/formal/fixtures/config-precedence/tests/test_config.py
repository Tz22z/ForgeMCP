import pytest
from config import resolve_timeout


def test_explicit_value_wins() -> None:
    assert resolve_timeout(explicit=5, environment="10", config_file=20) == 5


def test_default_is_used_when_sources_are_absent() -> None:
    assert resolve_timeout(default=45) == 45


def test_invalid_explicit_value_is_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_timeout(explicit=0)
