"""Payment Orchestrator client. Public, no auth."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import Payment
from .base import BaseClient


class OrchestratorClient(BaseClient):
    service = "payment-orchestrator"

    def __init__(self, config: Config):
        super().__init__(config.orchestrator_url, config)

    def create_payment(self, account_id: str, amount: str, destination: str) -> Payment:
        body = {"account_id": account_id, "amount": amount, "destination": destination}
        return Payment.model_validate(self.post_json("/payments", json=body))

    def get_payment(self, payment_id: str) -> Payment:
        return Payment.model_validate(self.get_json(f"/payments/{payment_id}"))

    def payment_events(self, payment_id: str) -> list[dict[str, Any]]:
        return self.get_json(f"/payments/{payment_id}/events")

    def reconcile(self, payment_id: str) -> Payment:
        return Payment.model_validate(
            self.post_json(f"/payments/{payment_id}/reconcile", expect=(200,))
        )

    def callback(
        self, payment_id: str, provider: str, provider_reference: str, outcome: str
    ) -> dict[str, Any]:
        body = {
            "provider": provider,
            "provider_reference": provider_reference,
            "outcome": outcome,
        }
        return self.post_json(f"/payments/{payment_id}/callback", json=body, expect=(200,))

    def publish_outbox(self, limit: int = 200) -> dict[str, Any]:
        return self.post_json("/outbox/publish", params={"limit": limit}, expect=(200,))
