from decimal import Decimal

from checkout import quote


def test_pro_threshold_uses_gross_subtotal() -> None:
    result = quote(Decimal("50.00"), "pro")
    assert result["discount"] == Decimal("5.00")
    assert result["shipping"] == Decimal("0.00")
    assert result["total"] == Decimal("45.00")
