from decimal import Decimal


def discount_rate(customer_tier: str) -> Decimal:
    """Return the contractual discount for a customer tier."""
    rates = {
        "basic": Decimal("0.00"),
        "pro": Decimal("0.05"),
    }
    return rates.get(customer_tier, Decimal("0.00"))


def subtotal(items: list[dict[str, object]]) -> Decimal:
    return sum(
        (Decimal(str(item["unit_price"])) * int(item["quantity"]) for item in items),
        start=Decimal("0.00"),
    )
