"""Typed black-box clients, one per ABS service.

Each client wraps a single service's public HTTP surface as described in
../docs/SERVICE_CATALOGUE.md. Clients speak only that surface: no service database, no
queue, no private helper.
"""

from .analytics import AnalyticsClient
from .ledger import LedgerClient
from .notification import NotificationClient
from .orchestrator import OrchestratorClient
from .risk import RiskClient

__all__ = [
    "LedgerClient",
    "OrchestratorClient",
    "RiskClient",
    "NotificationClient",
    "AnalyticsClient",
]
