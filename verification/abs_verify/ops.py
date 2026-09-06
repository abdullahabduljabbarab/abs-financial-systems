"""Controlled operator tooling.

Some scenarios need an action on the deployment that no service API exposes, such
as running the analytics refresh job (projections refresh off the ingest path).
These are performed here through gcloud, never by reaching inside a service. This
module is the seam where the harness acts as an operator, and it is kept separate
from the black-box clients on purpose.
"""

from __future__ import annotations

import subprocess

from .config import Config


class OperatorError(RuntimeError):
    pass


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
