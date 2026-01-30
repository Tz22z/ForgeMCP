class ChargeLedger:
    def __init__(self) -> None:
        self._receipts: dict[str, str] = {}

    def get(self, idempotency_key: str) -> str | None:
        return self._receipts.get(idempotency_key)

    def record(self, idempotency_key: str, receipt: str) -> None:
        self._receipts[idempotency_key] = receipt
