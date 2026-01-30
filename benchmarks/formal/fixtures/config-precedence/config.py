def _positive(value: int, source: str) -> int:
    if value < 1:
        raise ValueError(f"{source} timeout must be positive")
    return value


def resolve_timeout(
    *,
    explicit: int | None = None,
    environment: str | None = None,
    config_file: int | None = None,
    default: int = 30,
) -> int:
    if explicit is not None:
        return _positive(explicit, "explicit")
    if config_file is not None:
        return _positive(config_file, "config")
    if environment is not None:
        return _positive(int(environment), "environment")
    return _positive(default, "default")
