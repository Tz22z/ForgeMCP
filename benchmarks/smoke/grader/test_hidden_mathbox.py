from mathbox import double


def test_double_negative_value() -> None:
    assert double(-3) == -6


def test_double_zero() -> None:
    assert double(0) == 0
