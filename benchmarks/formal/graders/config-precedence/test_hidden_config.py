from config import resolve_timeout


def test_environment_wins_over_config_file() -> None:
    assert resolve_timeout(environment="12", config_file=25, default=60) == 12


def test_config_file_wins_over_default() -> None:
    assert resolve_timeout(config_file=25, default=60) == 25
