"""SYS-V-003: Financial operation retry safety.

Covers ABS-REQ-002 (a payment produces its financial effect at most once) and
ABS-REQ-005 (a payment maps to a deterministic, idempotently keyed set of ledger
transactions; retries never add to the set).

This is deliberately not a duplicate-HTTP-request test: POST /payments is not
idempotent. The at-most-once property is proven where it holds, the ledger effect.
For a settled payment: the customer-side leg is exactly one reserve keyed
`payment:{id}:reserve` (and no release), and the payment's capture is a single,
stable capture id. Ledger idempotency itself is proven directly: replaying a
transaction with an already-used idempotency key returns the same transaction and
does not move money twice.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from ..evidence import Evidence
from .base import Scenario, World

_AMOUNT = "10.00"
_FUND = "500.00"
_DESTINATION = "sys-v-003-merchant"


class SysV003(Scenario):
    id = "sys-v-003"
    title = "Financial operation retry safety"
    covers = ["ABS-REQ-002", "ABS-REQ-005"]

    def run(self, world: World, ev: Evidence) -> None:
        world.ledger.login()
        account_id = world.funded_account("sys-v-003", _FUND)
        ev.step("funded_account", account_id=account_id, funded=_FUND)

        payment, states = world.drive_settled_payment(account_id, _AMOUNT, _DESTINATION)
        ev.step("settle_attempts", states=states)
        ev.require(
            "a payment settled",
            payment is not None,
            f"states={states}",
        )
        assert payment is not None
        ev.step(
            "settled_payment",
            payment_id=payment.id,
            reserve_tx_id=payment.reserve_tx_id,
            capture_tx_id=payment.capture_tx_id,
        )

        # --- the deterministic keyed set, customer-side ---------------------
        # Reserve and release are the legs that touch the customer account; capture
        # is suspense to settlement and does not appear here. On the fresh account,
        # exactly one reserve keyed to the payment, and no release for a settled one.
        customer_txns = world.ledger.list_transactions(account_id=account_id)
        keyed = [t for t in customer_txns if payment.id in t.idempotency_key]
        reserve = [t for t in keyed if t.idempotency_key == f"payment:{payment.id}:reserve"]
        release = [t for t in keyed if t.idempotency_key == f"payment:{payment.id}:release"]
        ev.step("customer_keyed_txns", keys=[t.idempotency_key for t in keyed])
        ev.require(
            "exactly one reserve keyed to the payment, and no release",
            len(reserve) == 1 and len(release) == 0,
            f"reserve={len(reserve)} release={len(release)} keys={[t.idempotency_key for t in keyed]}",
            covers=["ABS-REQ-005"],
        )
        ev.require(
            "the settled payment carries a single capture id",
            bool(payment.capture_tx_id) and payment.reserve_tx_id != payment.capture_tx_id,
            f"reserve={payment.reserve_tx_id} capture={payment.capture_tx_id}",
            covers=["ABS-REQ-002"],
        )

        # --- ledger idempotency: a replayed key does not move money twice ----
        key = f"sys-v-003-idem-{uuid.uuid4().hex[:8]}"
        balance_before = world.ledger.balance(account_id).balance
        first = world.ledger.deposit(account_id, "1.00", idempotency_key=key)
        replay = world.ledger.deposit(account_id, "1.00", idempotency_key=key)
        balance_after = world.ledger.balance(account_id).balance
        ev.step(
            "idempotent_replay",
            first_tx=first.id,
            replay_tx=replay.id,
            balance_before=balance_before,
            balance_after=balance_after,
        )
        ev.require(
            "replaying an idempotency key returns the same transaction",
            first.id == replay.id,
            f"first={first.id} replay={replay.id}",
            covers=["ABS-REQ-002"],
        )
        ev.require(
            "the replayed transaction moves money only once",
            balance_after - balance_before == Decimal("1.00"),
            f"delta={balance_after - balance_before}, expected 1.00",
            covers=["ABS-REQ-002"],
        )
