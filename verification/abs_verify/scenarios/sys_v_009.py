"""SYS-V-009: Duplicate delivery tolerance.

Covers ABS-REQ-008 (consumers must tolerate duplicate delivery).

A settled payment first produces its normal notification and analytics records. The
same `payment.settled` event is then re-published to its topic as controlled operator
tooling, so both sinks receive it a second time. Each consumer deduplicates on
`event_id`: the notification delivery set is unchanged (one per channel), and the
analytics trace still shows the event once.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

from ..evidence import Evidence
from ..ops import publish_to_topic
from .base import Scenario, World

_FUND = "500.00"
_AMOUNT = "10.00"
_DESTINATION = "sys-v-009-merchant"
_PAYMENT_EVENTS_TOPIC = "payment-events"


class SysV009(Scenario):
    id = "sys-v-009"
    title = "Duplicate delivery tolerance"
    covers = ["ABS-REQ-008"]

    def run(self, world: World, ev: Evidence) -> None:
        world.ledger.login()
        world.warm_risk_feed(ev)
        account_id = world.funded_account("sys-v-009", _FUND)

        payment, states = world.drive_settled_payment(account_id, _AMOUNT, _DESTINATION)
        ev.require("a payment settled", payment is not None, f"states={states}")
        assert payment is not None
        correlation_id = payment.correlation_id

        world.orchestrator.publish_outbox()

        # Baseline: the settled event is delivered on both channels.
        notifications = world.notification.poll_until(
            fetch=lambda: world.notification.notifications(payment.id),
            predicate=lambda n: any(d.status == "delivered" for d in n.deliveries),
            describe="the settled payment's notifications",
        )
        settled_event_id = next(d.event_id for d in notifications.deliveries if d.status == "delivered")
        baseline_channels = sorted(d.channel for d in notifications.deliveries)
        ev.step(
            "baseline",
            settled_event_id=settled_event_id,
            deliveries=len(notifications.deliveries),
            channels=baseline_channels,
        )

        # Analytics baseline for this event id.
        analytics_before = world.analytics.poll_until(
            fetch=lambda: world.analytics.events(correlation_id),
            predicate=lambda evs: any(e["event_id"] == settled_event_id for e in evs),
            describe="analytics to have ingested the settled event",
        )
        count_before = sum(1 for e in analytics_before if e["event_id"] == settled_event_id)
        ev.step("analytics_before", occurrences_of_settled_event=count_before)

        # Inject a duplicate: re-publish the same payment.settled event (same
        # event_id) to the topic both sinks consume.
        duplicate = {
            "event_id": settled_event_id,
            "event_type": "payment.settled",
            "event_version": 1,
            "occurred_at": datetime.now(tz=timezone.utc).isoformat(),
            "producer": "payment-orchestrator",
            "correlation_id": correlation_id,
            "causation_id": settled_event_id,
            "aggregate_id": payment.id,
            "payload": {"payment_id": payment.id, "account_id": account_id},
        }
        publish_to_topic(world.config, _PAYMENT_EVENTS_TOPIC, json.dumps(duplicate))
        ev.step("duplicate_published", event_id=settled_event_id, uniquifier=str(uuid.uuid4()))
        time.sleep(world.config.poll_interval * 3)

        # Notification deduplicates on (event_id, channel): the delivery set is
        # unchanged.
        after = world.notification.notifications(payment.id)
        after_channels = sorted(d.channel for d in after.deliveries)
        ev.step("notifications_after_duplicate", deliveries=len(after.deliveries), channels=after_channels)
        ev.require(
            "the duplicate produces no additional notification delivery",
            after_channels == baseline_channels
            and len(after_channels) == len(set(after_channels)),
            f"before={baseline_channels} after={after_channels}",
            covers=["ABS-REQ-008"],
        )

        # Analytics deduplicates on event_id: the event still appears once.
        analytics_after = world.analytics.events(correlation_id)
        count_after = sum(1 for e in analytics_after if e["event_id"] == settled_event_id)
        ev.step("analytics_after", occurrences_of_settled_event=count_after)
        ev.require(
            "the duplicate is recorded once in analytics, not twice",
            count_after == 1,
            f"occurrences={count_after}",
            covers=["ABS-REQ-008"],
        )
