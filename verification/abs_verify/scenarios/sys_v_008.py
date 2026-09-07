"""SYS-V-008: Sink failure does not touch money.

Covers ABS-REQ-006 (failure of notifications or analytics must not alter financial
state).

The notification consumer is taken offline by cutting its push subscriptions (not by
pretending Cloud Run scaling is downtime). With the sink down, a payment is settled:
it settles correctly, the customer is debited once, and the ledger audit passes,
proving settlement does not depend on the sink. Events published during the outage
are held by Pub/Sub; once the sink is restored, the backlog is delivered exactly
once, with no channel double-notified.
"""

from __future__ import annotations

import time
from decimal import Decimal

from ..evidence import Evidence
from ..ops import subscriptions_push_cut
from .base import Scenario, World

_FUND = "500.00"
_AMOUNT = "10.00"
_DESTINATION = "sys-v-008-merchant"
_NOTIFICATION_SUBSCRIPTIONS = [
    "payment-events-to-notification",
    "risk-events-to-notification",
]


class SysV008(Scenario):
    id = "sys-v-008"
    title = "Sink failure does not touch money"
    covers = ["ABS-REQ-006"]

    def run(self, world: World, ev: Evidence) -> None:
        world.ledger.login()
        # Warm risk's feed first (with its own subscription, which stays up) so the
        # settle is allowed through; the sink outage below is unrelated to risk.
        world.warm_risk_feed(ev)
        account_id = world.funded_account("sys-v-008", _FUND)
        funded = world.ledger.balance(account_id).balance
        ev.step("funded_account", account_id=account_id, balance=funded)

        with subscriptions_push_cut(world.config, _NOTIFICATION_SUBSCRIPTIONS, ev):
            payment, states = world.drive_settled_payment(account_id, _AMOUNT, _DESTINATION)
            ev.step("settle_attempts", states=states)
            ev.require(
                "a payment settles while the notification sink is down",
                payment is not None,
                f"states={states}",
                covers=["ABS-REQ-006"],
            )
            assert payment is not None

            balance_after = world.ledger.balance(account_id).balance
            ev.require(
                "the customer is debited correctly with the sink down",
                funded - balance_after == Decimal(_AMOUNT),
                f"delta={funded - balance_after}, expected {_AMOUNT}",
                covers=["ABS-REQ-006"],
            )
            verify = world.ledger.audit_verify()
            ev.require(
                "the ledger audit passes with the sink down",
                verify.get("status") == "pass",
                f"status={verify.get('status')}",
                covers=["ABS-REQ-006"],
            )

            # Publish the payment events; the notification push is cut, so Pub/Sub
            # holds them rather than delivering.
            world.orchestrator.publish_outbox()
            time.sleep(world.config.poll_interval)
            during = world.notification.notifications(payment.id)
            ev.step("notifications_during_outage", count=len(during.deliveries))
            ev.check(
                "no notification is delivered while the sink is down",
                len(during.deliveries) == 0,
                f"deliveries={len(during.deliveries)}",
            )

        # Sink restored: Pub/Sub redelivers the held backlog.
        delivered = world.notification.poll_until(
            fetch=lambda: world.notification.notifications(payment.id),
            predicate=lambda n: any(d.status == "delivered" for d in n.deliveries),
            timeout=180,
            describe="the notification backlog to drain after the sink is restored",
        )
        channels = sorted(d.channel for d in delivered.deliveries)
        ev.step("notifications_after_restore", channels=channels, count=len(delivered.deliveries))
        ev.require(
            "the held notification is delivered once the sink is restored",
            any(d.status == "delivered" for d in delivered.deliveries),
            f"deliveries={[(d.channel, d.status) for d in delivered.deliveries]}",
            covers=["ABS-REQ-006"],
        )
        ev.check(
            "no channel is double-notified (one delivery per channel)",
            len(channels) == len(set(channels)),
            f"channels={channels}",
        )
