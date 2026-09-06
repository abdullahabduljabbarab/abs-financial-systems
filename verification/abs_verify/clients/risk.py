"""Risk Engine client. Public business API; the pubsub consumer is not called here."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import Decision
from .base import BaseClient


class RiskClient(BaseClient):
    service = "risk-engine"

    def __init__(self, config: Config):
        super().__init__(config.risk_url, config)

    def evaluate(self, body: dict[str, Any]) -> Decision:
        return Decision.model_validate(self.post_json("/risk/evaluate", json=body, expect=(200,)))

    def get_decision(self, evaluation_id: str) -> Decision:
        return Decision.model_validate(self.get_json(f"/decisions/{evaluation_id}"))

    def publish_outbox(self, limit: int = 200) -> dict[str, Any]:
        return self.post_json("/outbox/publish", params={"limit": limit}, expect=(200,))
