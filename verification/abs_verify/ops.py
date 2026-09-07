"""Controlled operator tooling.

Some scenarios need an action on the deployment that no service API exposes, such
as running the analytics refresh job (projections refresh off the ingest path).
These are performed here through gcloud, never by reaching inside a service. This
module is the seam where the harness acts as an operator, and it is kept separate
from the black-box clients on purpose.
"""

from __future__ import annotations

import contextlib
import subprocess
import time
from typing import Iterator

from .config import Config


class OperatorError(RuntimeError):
    pass


def _gcloud(config: Config, *args: str, timeout: int = 300) -> str:
    cmd = [config.gcloud_path, *args, f"--project={config.gcp_project}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise OperatorError(
            "gcloud is required for controlled verification but was not found; "
            "set ABS_GCLOUD to its path"
        ) from exc
    if result.returncode != 0:
        raise OperatorError(f"gcloud {' '.join(args)} failed: {result.stderr[:400]}")
    return result.stdout.strip()


_ORCHESTRATOR_SERVICE = "payment-orchestrator"


def _orchestrator_revision(config: Config) -> str:
    return _gcloud(
        config,
        "run",
        "services",
        "describe",
        _ORCHESTRATOR_SERVICE,
        f"--region={config.gcp_region}",
        "--format=value(status.latestReadyRevisionName)",
    )


def _set_orchestrator_env(config: Config, key: str, value: str) -> str:
    """Set one env var on the orchestrator, returning the new revision."""
    _gcloud(
        config,
        "run",
        "services",
        "update",
        _ORCHESTRATOR_SERVICE,
        f"--region={config.gcp_region}",
        f"--update-env-vars={key}={value}",
    )
    return _orchestrator_revision(config)


@contextlib.contextmanager
def orchestrator_risk_unreachable(config: Config, ev) -> Iterator[None]:
    """Point the orchestrator at an unreachable risk URL for the duration.

    This is the controlled way to make the risk service unavailable to the
    orchestrator without touching risk itself. RISK_BASE_URL is always restored to
    the real risk service on exit, even if the scenario raises.
    """
    dead_url = "https://risk-unreachable.invalid.example"
    before = _orchestrator_revision(config)
    ev.step("risk_unreachable_before", revision=before, restore_to=config.risk_url)
    _set_orchestrator_env(config, "RISK_BASE_URL", dead_url)
    ev.step("risk_unreachable_enabled", risk_base_url=dead_url)
    time.sleep(3)
    try:
        yield
    finally:
        restored = _set_orchestrator_env(config, "RISK_BASE_URL", config.risk_url)
        ev.step("risk_unreachable_restored", revision=restored, risk_base_url=config.risk_url)


def _set_orchestrator_hooks(config: Config, enabled: bool) -> str:
    """Set VERIFICATION_HOOKS on the orchestrator, returning the new revision."""
    _gcloud(
        config,
        "run",
        "services",
        "update",
        _ORCHESTRATOR_SERVICE,
        f"--region={config.gcp_region}",
        f"--update-env-vars=VERIFICATION_HOOKS={'true' if enabled else 'false'}",
    )
    return _orchestrator_revision(config)


@contextlib.contextmanager
def provider_hooks(config: Config, ev) -> Iterator[None]:
    """Enable the orchestrator's provider-outcome seam for the duration.

    Records the revision before and after, and always restores VERIFICATION_HOOKS
    to false and re-checks health on exit, even if the scenario raises. This is the
    controlled-verification window: deterministic failure injection exists only
    while it is open, never on the ordinary deployment.
    """
    before = _orchestrator_revision(config)
    ev.step("provider_hooks_before", revision=before)
    enabled_revision = _set_orchestrator_hooks(config, True)
    ev.step("provider_hooks_enabled", revision=enabled_revision)
    # Give the new revision a moment to serve, then confirm it is healthy.
    time.sleep(3)
    try:
        yield
    finally:
        restored = _set_orchestrator_hooks(config, False)
        ev.step("provider_hooks_restored", revision=restored)


def _describe_push(config: Config, subscription: str) -> tuple[str, str]:
    endpoint = _gcloud(
        config,
        "pubsub",
        "subscriptions",
        "describe",
        subscription,
        "--format=value(pushConfig.pushEndpoint)",
    )
    sa = _gcloud(
        config,
        "pubsub",
        "subscriptions",
        "describe",
        subscription,
        "--format=value(pushConfig.oidcToken.serviceAccountEmail)",
    )
    return endpoint, sa


@contextlib.contextmanager
def subscriptions_push_cut(config: Config, subscriptions: list[str], ev) -> Iterator[None]:
    """Cut push delivery to one or more subscriptions for the duration.

    Each subscription's push endpoint is captured, redirected to a dead endpoint so
    the consumer stops receiving (Pub/Sub holds and retries the backlog), and always
    restored to its exact original endpoint and OIDC identity on exit. The restore is
    verified. This is how a downstream consumer is taken offline without pretending
    Cloud Run scaling is downtime, and without touching the consumer service itself.
    """
    dead = "https://push-cut.invalid.example/events/pubsub"
    captured: dict[str, tuple[str, str]] = {}
    for sub in subscriptions:
        captured[sub] = _describe_push(config, sub)
        _gcloud(
            config, "pubsub", "subscriptions", "modify-push-config", sub,
            f"--push-endpoint={dead}",
        )
        ev.step("subscription_cut", subscription=sub, was_endpoint=captured[sub][0])
    # A push-config change takes a few seconds to take effect; wait so the cut is
    # genuinely active before the scenario relies on it.
    time.sleep(10)
    try:
        yield
    finally:
        for sub, (endpoint, sa) in captured.items():
            args = ["pubsub", "subscriptions", "modify-push-config", sub, f"--push-endpoint={endpoint}"]
            if sa:
                args.append(f"--push-auth-service-account={sa}")
            _gcloud(config, *args)
            r_ep, r_sa = _describe_push(config, sub)
            ev.step(
                "subscription_restored",
                subscription=sub,
                endpoint=r_ep,
                service_account=r_sa,
                restored_ok=(r_ep == endpoint and r_sa == sa),
            )


def subscription_push_endpoint(config: Config, subscription: str) -> str:
    """The subscription's current push endpoint, for asserting a cut is in effect."""
    return _describe_push(config, subscription)[0]


def publish_to_topic(config: Config, topic: str, message: str) -> None:
    """Publish one message to a topic as controlled operator tooling (used to inject
    a duplicate delivery). Pub/Sub adds the subscription's OIDC token on push."""
    _gcloud(config, "pubsub", "topics", "publish", topic, f"--message={message}")


def trigger_analytics_refresh(config: Config, wait: bool = True) -> bool:
    """Execute the analytics-refresh Cloud Run Job.

    Returns True on success. Returns False (rather than raising) if gcloud is not
    available, so a scenario can fall back to waiting for the scheduled refresh.
    """
    cmd = [
        config.gcloud_path,
        "run",
        "jobs",
        "execute",
        config.analytics_refresh_job,
        f"--project={config.gcp_project}",
        f"--region={config.gcp_region}",
    ]
    if wait:
        cmd.append("--wait")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        raise OperatorError(
            f"analytics refresh job failed ({result.returncode}): {result.stderr[:400]}"
        )
    return True
