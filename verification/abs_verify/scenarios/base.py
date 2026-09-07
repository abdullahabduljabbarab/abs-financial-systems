"""Scenario base and the shared client world."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from ..clients import (
    AnalyticsClient,
    LedgerClient,
    NotificationClient,
    OrchestratorClient,
    RiskClient,
)
from ..config import Config
from ..evidence import Evidence


@dataclass
class World:
    """The five live services, as black-box clients, for one run."""

    config: Config
    ledger: LedgerClient
    orchestrator: OrchestratorClient
    risk: RiskClient
    notification: NotificationClient
    analytics: AnalyticsClient

    @classmethod
    def from_config(cls, config: Config) -> "World":
        return cls(
            config=config,
            ledger=LedgerClient(config),
            orchestrator=OrchestratorClient(config),
            risk=RiskClient(config),
            notification=NotificationClient(config),
            analytics=AnalyticsClient(config),
        )

    def close(self) -> None:
        for client in (
            self.ledger,
            self.orchestrator,
            self.risk,
            self.notification,
            self.analytics,
        ):
            client.close()

    # --- shared arrange helpers --------------------------------------------

    def funded_account(self, name_prefix: str, amount: str) -> str:
        """Create a fresh account and deposit `amount` into it. Returns its id."""
        account = self.ledger.create_account(f"{name_prefix}-{uuid.uuid4().hex[:8]}")
        self.ledger.deposit(
            account.id, amount, idempotency_key=f"fund-{account.id}-{uuid.uuid4().hex[:8]}"
        )
        return account.id

    def drive_settled_payment(
        self, account_id: str, amount: str, destination: str, max_attempts: int = 25
    ):
        """Create payments until one settles; return (payment, [states seen]).

        POST /payments is stochastic (provider simulator plus risk), so a settle is
        driven by bounded retry. A deterministic provider-outcome seam (M2) will make
        this a single call. `payment` is None if none settled within max_attempts.
        """
        states: list[str] = []
        for _ in range(max_attempts):
            payment = self.orchestrator.create_payment(account_id, amount, destination)
            states.append(payment.state)
            if payment.state == "settled":
                return payment, states
        return None, states


class Scenario:
    """Base class for a system verification scenario."""

    id: str = "sys-v-000"
    title: str = "unnamed"
    covers: list[str] = []

    def run(self, world: World, ev: Evidence) -> None:  # pragma: no cover - interface
        raise NotImplementedError
