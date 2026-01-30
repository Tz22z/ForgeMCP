from retry_budget import should_retry


def test_retry_boundary_counts_total_attempts() -> None:
    assert should_retry(1, 3)
    assert should_retry(2, 3)
    assert not should_retry(3, 3)
    assert not should_retry(4, 3)
