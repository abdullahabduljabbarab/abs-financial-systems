"""Notification Service client. Strict sink; only its read API is called here."""

from __future__ import annotations

from ..config import Config
from ..models import Notifications
from .base import BaseClient


class NotificationClient(BaseClient):
    service = "notification-service"

    def __init__(self, config: Config):
        super().__init__(config.notification_url, config)

    def notifications(self, payment_id: str) -> Notifications:
        return Notifications.model_validate(self.get_json(f"/notifications/{payment_id}"))
