"""BFF configuration: the upstream service URLs, env-driven with live defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

_DEFAULT_HOST = "https://{svc}-eppidgbmxa-nw.a.run.app"


def _url(env_key: str, service: str) -> str:
    return os.environ.get(env_key, _DEFAULT_HOST.format(svc=service)).rstrip("/")


@dataclass(frozen=True)
class Config:
    ledger_url: str = field(default_factory=lambda: _url("PORTAL_LEDGER_URL", "ledger-api"))
    orchestrator_url: str = field(
        default_factory=lambda: _url("PORTAL_ORCHESTRATOR_URL", "payment-orchestrator")
    )
    risk_url: str = field(default_factory=lambda: _url("PORTAL_RISK_URL", "risk-engine"))
    notification_url: str = field(
        default_factory=lambda: _url("PORTAL_NOTIFICATION_URL", "notification-service")
    )
    analytics_url: str = field(
        default_factory=lambda: _url("PORTAL_ANALYTICS_URL", "analytics-service")
    )
    http_timeout: float = field(
        default_factory=lambda: float(os.environ.get("PORTAL_HTTP_TIMEOUT", "15"))
    )

    def services(self) -> dict[str, str]:
        """The upstream services by name, in display order."""
        return {
            "ledger-api": self.ledger_url,
            "payment-orchestrator": self.orchestrator_url,
            "risk-engine": self.risk_url,
            "notification-service": self.notification_url,
            "analytics-service": self.analytics_url,
        }


def load_config() -> Config:
    return Config()
