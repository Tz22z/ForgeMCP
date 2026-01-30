from decimal import Decimal
from typing import Protocol

from ledger import ChargeLedger


class Gateway(Protocol):
    def charge(self, amount: Decimal) -> str: ...


class PaymentProcessor:
    def __init__(self, gateway: Gateway, ledger: ChargeLedger) -> None:
        self.gateway = gateway
        self.ledger = ledger

    def charge(self, idempotency_key: str, amount: Decimal) -> str:
        receipt = self.gateway.charge(amount)
        self.ledger.record(idempotency_key, receipt)
        return receipt
