"""SYS-V-005: Provider timeout pins and reconciles.

Covers ABS-REQ-004 (a provider timeout is not a failure) and ABS-REQ-012 (a timed-out
payment is pinned to its provider, never routed to another, until reconciliation).

A provider timeout is a synchronous result at submit time that drives the payment to
`unknown` with its reservation held. It is produced deterministically through the
controlled provider-outcome seam (a `verify-outcome:timeout` destination), not by
waiting for a stochastic provider. Reconciliation then resolves it against the same
provider to a terminal state with the matching ledger movement.
"""

from __future__ import annotations

from decimal import Decimal

from ..evidence import Evidence
from .base import Scenario, World

_FUND = "500.00"
_AMOUNT = "10.00"
_TIMEOUT_DESTINATION = "verify-outcome:timeout"


class SysV005(Scenario):
    id = "sys-v-005"
    title = "Provider timeout pins and reconciles"
    covers = ["ABS-REQ-004", "ABS-REQ-012"]
    requires_provider_hooks = True

    def run(self, world: World, ev: Evidence) -> None:
        world.ledger.login()
        account_id = world.funded_account("sys-v-005", _FUND)
        funded = world.ledger.balance(account_id).balance
        ev.step("funded_account", account_id=account_id, balance=funded)

        # Ensure risk allows the payment through to the provider: a stale risk feed
        # would block a fresh account before it ever reaches the forced timeout.
        world.warm_risk_feed(ev)

        payment = world.orchestrator.create_payment(account_id, _AMOUNT, _TIMEOUT_DESTINATION)
        ev.step(
            "payment",
            payment_id=payment.id,
            state=payment.state,
            provider=payment.provider,
            reserve_tx_id=payment.reserve_tx_id,
        )
        ev.require(
            "a timed-out payment goes to unknown",
            payment.state == "unknown",
            f"state={payment.state}",
            covers=["ABS-REQ-004"],
        )
        ev.require(
            "the reservation is held: reserved, not captured or released",
            bool(payment.reserve_tx_id)
            and payment.capture_tx_id is None
            and payment.release_tx_id is None,
            f"reserve={payment.reserve_tx_id} capture={payment.capture_tx_id} release={payment.release_tx_id}",
            covers=["ABS-REQ-004"],
        )
        balance_held = world.ledger.balance(account_id).balance
        ev.require(
            "funds are held out of the account while unknown",
            funded - balance_held == Decimal(_AMOUNT),
            f"held={funded - balance_held}, expected {_AMOUNT}",
            covers=["ABS-REQ-004"],
        )
        pinned_provider = payment.provider

        # --- reconcile against the same provider --------------------------
        reconciled = world.orchestrator.reconcile(payment.id)
        ev.step(
            "reconciled",
            state=reconciled.state,
            provider=reconciled.provider,
            capture_tx_id=reconciled.capture_tx_id,
            release_tx_id=reconciled.release_tx_id,
        )
        ev.require(
            "reconciliation stays on the original provider, no fallback",
            reconciled.provider == pinned_provider,
            f"pinned={pinned_provider} after={reconciled.provider}",
            covers=["ABS-REQ-012"],
        )
        ev.require(
            "reconciliation resolves to a terminal state",
            reconciled.state in ("settled", "failed"),
            f"state={reconciled.state}",
            covers=["ABS-REQ-004"],
        )

        balance_final = world.ledger.balance(account_id).balance
        if reconciled.state == "settled":
            ev.require(
                "a settled reconcile captures the held funds",
                bool(reconciled.capture_tx_id) and funded - balance_final == Decimal(_AMOUNT),
                f"capture={reconciled.capture_tx_id} balance_delta={funded - balance_final}",
                covers=["ABS-REQ-012"],
            )
        else:
            ev.require(
                "a failed reconcile releases the held funds back to the customer",
                bool(reconciled.release_tx_id) and balance_final == funded,
                f"release={reconciled.release_tx_id} final={balance_final} funded={funded}",
                covers=["ABS-REQ-012"],
            )
