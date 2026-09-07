"""Analytics Service client. Strict sink; read projections plus watermark."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import Watermark
from .base import BaseClient


class AnalyticsClient(BaseClient):
    service = "analytics-service"

    def __init__(self, config: Config):
        super().__init__(config.analytics_url, config)

    def overview(self) -> dict[str, Any]:
        return self.get_json("/analytics/overview")

    def payments(self) -> dict[str, Any]:
        return self.get_json("/analytics/payments")

    def account(self, account_id: str) -> dict[str, Any]:
        """Per-account projection. Nests the projection under `account`."""
        return self.get_json(f"/analytics/accounts/{account_id}")

    def watermark(self) -> Watermark:
        """The current raw-event watermark, read off any projection response."""
        return Watermark.model_validate(self.overview()["watermark"])

    def events(self, correlation_id: str) -> list[dict[str, Any]]:
        """Trace-safe event metadata analytics ingested under a correlation id."""
        return self.get_json("/analytics/events", params={"correlation_id": correlation_id})["events"]
