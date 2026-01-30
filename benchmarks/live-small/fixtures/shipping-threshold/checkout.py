from decimal import Decimal

from pricing import discount_rate

FREE_SHIPPING_MINIMUM = Decimal("50.00")
STANDARD_SHIPPING = Decimal("7.00")


def quote(subtotal: Decimal, customer_tier: str) -> dict[str, Decimal]:
    discount = (subtotal * discount_rate(customer_tier)).quantize(Decimal("0.01"))
    discounted = subtotal - discount
    shipping = Decimal("0.00") if discounted >= FREE_SHIPPING_MINIMUM else STANDARD_SHIPPING
    return {
        "subtotal": subtotal,
        "discount": discount,
        "shipping": shipping,
        "total": discounted + shipping,
    }
