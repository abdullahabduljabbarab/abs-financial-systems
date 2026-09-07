"""SYS-V-011: Cross-service traceability.

Covers ABS-REQ-009 (every cross-service operation remains traceable through one
correlation_id).

For one settled payment, the same correlation_id threads the payment, the
notification delivery, and, through analytics' event trace, the risk decision and
every downstream event. The ledger financial effect is reached through the
orchestrator's recorded reserve and capture transaction ids, because the ledger
transaction does not carry a correlation_id.
"""

from __future__ import annotations

from ..evidence import Evidence
from .base import Scenario, World

_AMOUNT = "10.00"
_FUND = "500.00"
_DESTINATION = "sys-v-011-merchant"


class SysV011(Scenario):
    id = "sys-v-011"
    title = "Cross-service traceability"
    covers = ["ABS-REQ-009"]

    def run(self, world: World, ev: Evidence) -> None:
        world.ledger.login()
        account_id = world.funded_account("sys-v-011", _FUND)

        payment, states = world.drive_settled_payment(account_id, _AMOUNT, _DESTINATION)
        ev.step("settle_attempts", states=states)
        ev.require("a payment settled", payment is not None, f"states={states}")
        assert payment is not None
        correlation_id = payment.correlation_id
        ev.step(
            "payment",
            payment_id=payment.id,
            correlation_id=correlation_id,
            reserve_tx_id=payment.reserve_tx_id,
            capture_tx_id=payment.capture_tx_id,
        )

        # Ledger leg: the financial effect is reachable through the recorded tx ids,
        # not a ledger correlation field.
        ev.require(
            "the payment records its ledger reserve and capture ids",
            bool(payment.reserve_tx_id) and bool(payment.capture_tx_id),
            f"reserve={payment.reserve_tx_id} capture={payment.capture_tx_id}",
            covers=["ABS-REQ-009"],
        )

        # Propagate.
        world.orchestrator.publish_outbox()
        world.risk.publish_outbox()
        world.ledger.publish_outbox()

        # Notification leg: the delivery carries the same correlation id.
        notifications = world.notification.poll_until(
            fetch=lambda: world.notification.notifications(payment.id),
            predicate=lambda n: any(d.correlation_id == correlation_id for d in n.deliveries),
            describe="a notification carrying the correlation id",
        )
        ev.step(
            "notification",
            correlation_ids=[d.correlation_id for d in notifications.deliveries],
        )
        ev.require(
            "the notification carries the payment's correlation id",
            any(d.correlation_id == correlation_id for d in notifications.deliveries),
            f"correlation_ids={[d.correlation_id for d in notifications.deliveries]}",
            covers=["ABS-REQ-009"],
        )

        # Analytics leg: the correlation trace includes the risk decision and the
        # payment events, proving the id threads through risk and analytics too.
        events = world.analytics.poll_until(
            fetch=lambda: world.analytics.events(correlation_id),
            predicate=lambda evs: any(e["event_type"] == "risk.evaluated" for e in evs),
            describe="the analytics correlation trace to include the risk decision",
        )
        types = sorted({e["event_type"] for e in events})
        producers = sorted({e.get("producer") for e in events})
        ev.step("analytics_trace", event_types=types, producers=producers, count=len(events))
        ev.require(
            "every event in the analytics trace carries the correlation id",
            len(events) > 0 and all(e["correlation_id"] == correlation_id for e in events),
            f"count={len(events)} ids={{{', '.join(sorted({str(e['correlation_id']) for e in events}))}}}",
            covers=["ABS-REQ-009"],
        )
        ev.require(
            "the trace spans the payment and the risk decision",
            "risk.evaluated" in types
            and any(t.startswith("payment.") for t in types),
            f"types={types}",
            covers=["ABS-REQ-009"],
        )
        ev.check(
            "the trace names both the orchestrator and the risk engine as producers",
            "payment-orchestrator" in producers and "risk-engine" in producers,
            f"producers={producers}",
        )
