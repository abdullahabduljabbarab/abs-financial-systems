"""SYS-V-013: Async risk feed unavailable.

Covers ABS-REQ-016 (the synchronous decision path is independent of the asynchronous
behavioural-state path, so lag or failure in event consumption cannot block or change
a decision already returned).

Distinct from SYS-V-007, which fails the risk service to the orchestrator: here the
risk engine's own behavioural feed is cut (its `payment-events` push subscription is
redirected away) while its synchronous decision API stays up. A direct
`POST /risk/evaluate` must still return a decision promptly, proving the sync path
does not depend on the async consumer.
"""

from __future__ import annotations

import time
import uuid

from ..evidence import Evidence
from ..ops import subscriptions_push_cut
from .base import Scenario, World

_RISK_FEED_SUBSCRIPTION = "payment-events-to-risk"


class SysV013(Scenario):
    id = "sys-v-013"
    title = "Async risk feed unavailable"
    covers = ["ABS-REQ-016"]

    def run(self, world: World, ev: Evidence) -> None:
        with subscriptions_push_cut(world.config, [_RISK_FEED_SUBSCRIPTION], ev):
            # The consumer is offline. The synchronous decision path must still work.
            started = time.monotonic()
            decision = world.risk.evaluate(
                {
                    "evaluation_id": str(uuid.uuid4()),
                    "payment_id": str(uuid.uuid4()),
                    "account_id": str(uuid.uuid4()),
                    "amount": "10.00",
                    "destination": "sys-v-013-" + uuid.uuid4().hex[:6],
                    "correlation_id": str(uuid.uuid4()),
                }
            )
            elapsed = time.monotonic() - started
            ev.step(
                "sync_decision_with_feed_down",
                decision=decision.decision,
                band=decision.band,
                score=decision.score,
                elapsed_seconds=round(elapsed, 3),
            )
            ev.require(
                "the synchronous decision path returns while the async feed is down",
                decision.decision in ("allow", "review", "block"),
                f"decision={decision.decision}",
                covers=["ABS-REQ-016"],
            )
            ev.require(
                "the synchronous decision returns promptly, not blocked on the feed",
                elapsed < 15,
                f"elapsed={elapsed:.3f}s",
                covers=["ABS-REQ-016"],
            )
            # A second evaluation is equally available: the sync path is not degraded.
            second = world.risk.evaluate(
                {
                    "evaluation_id": str(uuid.uuid4()),
                    "payment_id": str(uuid.uuid4()),
                    "account_id": str(uuid.uuid4()),
                    "amount": "20.00",
                    "destination": "sys-v-013-" + uuid.uuid4().hex[:6],
                    "correlation_id": str(uuid.uuid4()),
                }
            )
            ev.check(
                "a further decision is still served with the feed down",
                second.decision in ("allow", "review", "block"),
                f"decision={second.decision}",
            )
