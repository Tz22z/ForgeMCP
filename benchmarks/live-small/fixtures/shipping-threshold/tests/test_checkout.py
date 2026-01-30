from decimal import Decimal

from checkout import quote


def test_basic_customer_below_threshold_pays_shipping() -> None:
    result = quote(Decimal("40.00"), "basic")
    assert result["shipping"] == Decimal("7.00")
    assert result["total"] == Decimal("47.00")


def test_basic_customer_at_threshold_gets_free_shipping() -> None:
    result = quote(Decimal("50.00"), "basic")
    assert result["shipping"] == Decimal("0.00")
