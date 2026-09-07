"""SYS-V-002: Risk block holds money.

Covers ABS-REQ-011 (a provider is never called unless funds were reserved) and
ABS-REQ-013 (a bad risk decision never moves money).

A payment that risk blocks ends `rejected` with no financial effect: no reservation,
no provider contact, and the account balance unchanged. The block is made
deterministic by scoring above the block threshold: a high-value payment to a
watch-listed destination on a fresh account fires HIGH_VALUE + DESTINATION_REPUTATION
+ NEW_DESTINATION, which sums past `block_at`.
"""

from __future__ import annotations

from decimal import Decimal

from ..evidence import Evidence
from .base import Scenario, World

# Deterministic block inputs (risk-engine default rule config): amount at/above the
# high-value threshold, to a destination on the watch list, from a fresh account.
_AMOUNT = "5000.00"
_WATCHLISTED_DESTINATION = "known-fraud-dest"


class SysV002(Scenario):
    id = "sys-v-002"
    title = "Risk block holds money"
    covers = ["ABS-REQ-011", "ABS-REQ-013"]

    def run(self, world: World, ev: Evidence) -> None:
        world.ledger.login()

        # A fresh, unfunded account: a block must not depend on, or touch, funds.
        account = world.ledger.create_account("sys-v-002-" + _rand())
        ev.step("account", account_id=account.id)
        balance_before = world.ledger.balance(account.id).balance
        ev.require(
            "fresh account starts at zero",
            balance_before == Decimal("0"),
            f"balance={balance_before}",
        )

        payment = world.orchestrator.create_payment(account.id, _AMOUNT, _WATCHLISTED_DESTINATION)
        ev.step(
            "payment",
            payment_id=payment.id,
            state=payment.state,
            provider=payment.provider,
            reserve_tx_id=payment.reserve_tx_id,
        )

        ev.require(
            "risk-blocked payment is rejected",
            payment.state == "rejected",
            f"state={payment.state}",
            covers=["ABS-REQ-013"],
        )
        ev.require(
            "no reservation and no provider contact",
            payment.reserve_tx_id is None
            and payment.capture_tx_id is None
            and payment.release_tx_id is None
            and payment.provider is None,
            f"reserve={payment.reserve_tx_id} capture={payment.capture_tx_id} "
            f"release={payment.release_tx_id} provider={payment.provider}",
            covers=["ABS-REQ-011"],
        )

        balance_after = world.ledger.balance(account.id).balance
        ev.require(
            "account balance is unchanged by the blocked payment",
            balance_after == balance_before,
            f"before={balance_before} after={balance_after}",
            covers=["ABS-REQ-013"],
        )

        # The transition history should end at rejected via the risk gate, never
        # having entered reservation.
        events = world.orchestrator.payment_events(payment.id)
        states = [e.get("to_state") for e in events]
        ev.step("payment_states", states=states)
        ev.check(
            "payment never entered reservation",
            all(s not in ("reserving", "funds_reserved", "provider_pending") for s in states),
            f"states={states}",
        )


def _rand() -> str:
    import uuid

    return uuid.uuid4().hex[:8]
