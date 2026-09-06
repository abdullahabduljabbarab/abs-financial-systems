"""Harness configuration.

Everything is read from the environment with defaults that point at the live
ecosystem, so a bare `python -m abs_verify.runner sys-v-001` works out of the box
and CI can override any value.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

_DEFAULT_HOST = "https://{svc}-eppidgbmxa-nw.a.run.app"


def _url(env_key: str, service: str) -> str:
    return os.environ.get(env_key, _DEFAULT_HOST.format(svc=service))


@dataclass(frozen=True)
class Config:
    """Resolved configuration for one harness run."""

    ledger_url: str = field(default_factory=lambda: _url("ABS_LEDGER_URL", "ledger-api"))
    orchestrator_url: str = field(
        default_factory=lambda: _url("ABS_ORCHESTRATOR_URL", "payment-orchestrator")
    )
    risk_url: str = field(default_factory=lambda: _url("ABS_RISK_URL", "risk-engine"))
    notification_url: str = field(
        default_factory=lambda: _url("ABS_NOTIFICATION_URL", "notification-service")
    )
    analytics_url: str = field(
        default_factory=lambda: _url("ABS_ANALYTICS_URL", "analytics-service")
    )

    # The ledger is the only service that authenticates. These are the in-repo seed
    # admin credentials; override the password from the environment in any real run.
    ledger_admin_user: str = field(
        default_factory=lambda: os.environ.get("ABS_LEDGER_ADMIN_USER", "admin")
    )
    ledger_admin_password: str = field(
        default_factory=lambda: os.environ.get("ABS_LEDGER_ADMIN_PASSWORD", "admin123")
    )

    # The suspense and settlement system accounts are fixed orchestrator config, not
    # discoverable over the API. Supplied only for the optional settlement-credit
    # assertion in SYS-V-001; the scenario does not depend on them.
    suspense_account_id: str | None = field(
        default_factory=lambda: os.environ.get(
            "ABS_SUSPENSE_ACCOUNT_ID", "a0000000-0000-4000-8000-000000000001"
        )
    )
    settlement_account_id: str | None = field(
        default_factory=lambda: os.environ.get(
            "ABS_SETTLEMENT_ACCOUNT_ID", "a0000000-0000-4000-8000-000000000002"
        )
    )

    # TLS-inspecting networks break Python's default cert verification. Point this at
    # a combined CA bundle (certifi + the local root store) to run from such a machine.
    ca_bundle: str | None = field(
        default_factory=lambda: os.environ.get("ABS_CA_BUNDLE")
        or os.environ.get("REQUESTS_CA_BUNDLE")
    )

    # Analytics projections refresh off the ingest path, via a Cloud Run Job. The
    # harness triggers it as controlled operator tooling; this is how it calls gcloud.
    gcloud_path: str = field(
        default_factory=lambda: os.environ.get("ABS_GCLOUD", "gcloud")
    )
    gcp_project: str = field(
        default_factory=lambda: os.environ.get("ABS_GCP_PROJECT", "ledger-api-507618")
    )
    gcp_region: str = field(
        default_factory=lambda: os.environ.get("ABS_GCP_REGION", "europe-west2")
    )
    analytics_refresh_job: str = field(
        default_factory=lambda: os.environ.get("ABS_ANALYTICS_REFRESH_JOB", "analytics-refresh")
    )

    # Where immutable per-run evidence is written.
    evidence_dir: str = field(
        default_factory=lambda: os.environ.get("ABS_EVIDENCE_DIR", "evidence")
    )

    # Bounded-wait defaults for eventually-consistent assertions (seconds).
    http_timeout: float = field(
        default_factory=lambda: float(os.environ.get("ABS_HTTP_TIMEOUT", "30"))
    )
    poll_timeout: float = field(
        default_factory=lambda: float(os.environ.get("ABS_POLL_TIMEOUT", "60"))
    )
    poll_interval: float = field(
        default_factory=lambda: float(os.environ.get("ABS_POLL_INTERVAL", "3"))
    )

    @property
    def verify(self) -> str | bool:
        """The `verify` argument for httpx: a CA bundle path, or True."""
        return self.ca_bundle if self.ca_bundle else True


def load_config() -> Config:
    return Config()
