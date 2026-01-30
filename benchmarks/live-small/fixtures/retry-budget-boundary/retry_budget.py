def should_retry(attempt_number: int, max_attempts: int) -> bool:
    if attempt_number < 1:
        raise ValueError("attempt_number must be one-based")
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    return attempt_number <= max_attempts
