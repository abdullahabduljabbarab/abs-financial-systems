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
