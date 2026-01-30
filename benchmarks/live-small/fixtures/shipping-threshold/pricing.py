from decimal import Decimal


def discount_rate(customer_tier: str) -> Decimal:
    rates = {
        "basic": Decimal("0.00"),
        "pro": Decimal("0.10"),
    }
    return rates.get(customer_tier, Decimal("0.00"))
