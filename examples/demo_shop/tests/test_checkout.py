from decimal import Decimal

from shop.checkout import quote


def test_pro_tier_receives_contractual_ten_percent_discount() -> None:
    result = quote([{"unit_price": "40.00", "quantity": 1}], "pro")
    assert result["discount"] == Decimal("4.00")


def test_free_shipping_uses_pre_discount_subtotal() -> None:
    result = quote([{"unit_price": "25.00", "quantity": 2}], "pro")
    assert result["shipping"] == Decimal("0.00")
    assert result["total"] == Decimal("45.00")
