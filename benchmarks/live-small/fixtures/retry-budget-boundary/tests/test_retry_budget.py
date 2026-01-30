import pytest
from retry_budget import should_retry


def test_first_attempt_can_retry() -> None:
    assert should_retry(1, 3)


def test_invalid_attempt_is_rejected() -> None:
    with pytest.raises(ValueError):
        should_retry(0, 3)
