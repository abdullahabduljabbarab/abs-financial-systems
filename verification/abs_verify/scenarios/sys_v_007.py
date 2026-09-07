"""SYS-V-007: Risk service unavailable fails safe to review.

Covers ABS-REQ-013 (uncertainty in the risk decision must never permit money to
move; an unavailable risk engine holds the payment for review).

With the risk service made unreachable to the orchestrator (controlled injection:
RISK_BASE_URL pointed at a dead host, then restored), a payment is driven to
`risk_review` and held, with no reservation and no provider contact. It is neither
allowed nor auto-rejected. After risk is restored, a fresh evaluation succeeds,
proving risk is reachable again; the already-held payment stays held, because the
orchestrator exposes no operation to resume it.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from ..evidence import Evidence
from ..ops import orchestrator_risk_unreachable
from .base import Scenario, World

_FUND = "500.00"
_AMOUNT = "10.00"
_DESTINATION = "sys-v-007-merchant"


class SysV007(Scenario):
    id = "sys-v-007"
    title = "Risk service unavailable fails safe to review"
    covers = ["ABS-REQ-013"]

    def run(self, world: World, ev: Evidence) -> None:
        world.ledger.login()
        account_id = world.funded_account("sys-v-007", _FUND)
        balance_before = world.ledger.balance(account_id).balance
        ev.step("funded_account", account_id=account_id, balance=balance_before)

        with orchestrator_risk_unreachable(world.config, ev):
            payment = world.orchestrator.create_payment(account_id, _AMOUNT, _DESTINATION)
            ev.step(
                "payment_with_risk_down",
                payment_id=payment.id,
                state=payment.state,
                provider=payment.provider,
                reserve_tx_id=payment.reserve_tx_id,
            )
            ev.require(
                "a payment is held for review when risk is unavailable",
                payment.state == "risk_review",
                f"state={payment.state}",
                covers=["ABS-REQ-013"],
            )
            ev.require(
                "the held payment took no reservation and no provider contact",
                payment.reserve_tx_id is None
                and payment.capture_tx_id is None
                and payment.provider is None,
                f"reserve={payment.reserve_tx_id} capture={payment.capture_tx_id} provider={payment.provider}",
                covers=["ABS-REQ-013"],
            )
            balance_held = world.ledger.balance(account_id).balance
            ev.require(
                "the held payment moved no money (neither allowed nor rejected)",
                balance_held == balance_before,
                f"before={balance_before} during={balance_held}",
                covers=["ABS-REQ-013"],
            )

        # Risk restored: a fresh evaluation succeeds, proving it is reachable again.
        decision = world.risk.evaluate(
            {
                "evaluation_id": str(uuid.uuid4()),
                "payment_id": str(uuid.uuid4()),
                "account_id": str(uuid.uuid4()),
                "amount": "10.00",
                "destination": "post-restore-" + uuid.uuid4().hex[:6],
                "correlation_id": str(uuid.uuid4()),
            }
        )
        ev.step("post_restore_decision", decision=decision.decision, score=decision.score)
        ev.require(
            "risk is reachable again after restore",
            decision.decision in ("allow", "review", "block"),
            f"decision={decision.decision}",
        )

        # The held payment stays held: there is no public resume operation.
        held = world.orchestrator.get_payment(payment.id)
        ev.step("held_payment_after_restore", state=held.state)
        ev.check(
            "the previously held payment remains in review",
            held.state == "risk_review",
            f"state={held.state}",
        )
