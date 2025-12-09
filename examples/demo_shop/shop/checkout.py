from decimal import Decimal

from shop.pricing import discount_rate, subtotal

FREE_SHIPPING_MINIMUM = Decimal("50.00")
STANDARD_SHIPPING = Decimal("5.00")


def quote(items: list[dict[str, object]], customer_tier: str) -> dict[str, Decimal]:
    gross = subtotal(items)
    discount = (gross * discount_rate(customer_tier)).quantize(Decimal("0.01"))
    discounted = gross - discount
    shipping = Decimal("0.00") if discounted >= FREE_SHIPPING_MINIMUM else STANDARD_SHIPPING
    return {
        "subtotal": gross,
        "discount": discount,
        "shipping": shipping,
        "total": discounted + shipping,
    }
