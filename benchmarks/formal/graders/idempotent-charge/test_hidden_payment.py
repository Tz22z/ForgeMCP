from decimal import Decimal

from ledger import ChargeLedger
from payment import PaymentProcessor


class CountingGateway:
    def __init__(self) -> None:
        self.calls: list[Decimal] = []

    def charge(self, amount: Decimal) -> str:
        self.calls.append(amount)
        return f"receipt-{len(self.calls)}"


def test_duplicate_key_returns_original_without_second_charge() -> None:
    gateway = CountingGateway()
    processor = PaymentProcessor(gateway, ChargeLedger())

    first = processor.charge("same-key", Decimal("10.00"))
    second = processor.charge("same-key", Decimal("99.00"))

    assert first == second == "receipt-1"
    assert gateway.calls == [Decimal("10.00")]


def test_distinct_keys_charge_independently() -> None:
    gateway = CountingGateway()
    processor = PaymentProcessor(gateway, ChargeLedger())

    assert processor.charge("key-a", Decimal("10.00")) == "receipt-1"
    assert processor.charge("key-b", Decimal("11.00")) == "receipt-2"
    assert gateway.calls == [Decimal("10.00"), Decimal("11.00")]
