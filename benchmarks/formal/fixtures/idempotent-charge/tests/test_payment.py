from decimal import Decimal

from ledger import ChargeLedger
from payment import PaymentProcessor


class FakeGateway:
    def __init__(self) -> None:
        self.calls = 0

    def charge(self, amount: Decimal) -> str:
        self.calls += 1
        return f"receipt-{self.calls}-{amount}"


def test_first_charge_is_recorded() -> None:
    gateway = FakeGateway()
    ledger = ChargeLedger()
    processor = PaymentProcessor(gateway, ledger)

    receipt = processor.charge("order-1", Decimal("12.00"))

    assert gateway.calls == 1
    assert ledger.get("order-1") == receipt
