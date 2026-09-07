"""SYS-V-006: Reservation precedes any provider call.

Covers ABS-REQ-011 (a provider is never called unless funds were reserved).

A payment whose reservation cannot succeed ends `failed` with no provider contact.
The reservation failure is injected cleanly through the domain: a payment larger than
the account's funded balance cannot reserve, so the ledger rejects the reserve and
the orchestrator ends the payment failed without ever calling a provider.
"""

from __future__ import annotations

from decimal import Decimal

from ..evidence import Evidence
from .base import Scenario, World

_FUND = "5.00"
_AMOUNT = "10.00"  # deliberately more than the account holds
_DESTINATION = "sys-v-006-merchant"


class SysV006(Scenario):
    id = "sys-v-006"
    title = "Reservation precedes any provider call"
    covers = ["ABS-REQ-011"]

    def run(self, world: World, ev: Evidence) -> None:
        world.ledger.login()
        account_id = world.funded_account("sys-v-006", _FUND)
        balance_before = world.ledger.balance(account_id).balance
        ev.step("funded_account", account_id=account_id, funded=_FUND, balance=balance_before)
        ev.require(
            "account holds less than the payment amount",
            balance_before < Decimal(_AMOUNT),
            f"balance={balance_before} amount={_AMOUNT}",
        )

        payment = world.orchestrator.create_payment(account_id, _AMOUNT, _DESTINATION)
        ev.step(
            "payment",
            payment_id=payment.id,
            state=payment.state,
            provider=payment.provider,
            reserve_tx_id=payment.reserve_tx_id,
        )

        ev.require(
            "payment with a failed reservation ends failed",
            payment.state == "failed",
            f"state={payment.state}",
        )
        ev.require(
            "no provider was contacted and nothing was captured",
            payment.provider is None
            and payment.reserve_tx_id is None
            and payment.capture_tx_id is None,
            f"provider={payment.provider} reserve={payment.reserve_tx_id} capture={payment.capture_tx_id}",
        )

        balance_after = world.ledger.balance(account_id).balance
        ev.require(
            "balance is unchanged by the failed reservation",
            balance_after == balance_before,
            f"before={balance_before} after={balance_after}",
        )

        events = world.orchestrator.payment_events(payment.id)
        states = [e.get("to_state") for e in events]
        ev.step("payment_states", states=states)
        ev.check(
            "payment failed through reservation, never reaching a provider",
            "provider_pending" not in states and "capturing" not in states,
            f"states={states}",
        )
