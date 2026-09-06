"""SYS-V-001: Happy-path settlement.

Covers ABS-REQ-001 (only the ledger moves money) and ABS-REQ-005 (a payment maps to
a deterministic, idempotently keyed set of ledger transactions).

A funded payment settles end to end. The proof is the customer debit, the payment's
reserve and capture transaction ids, the ledger's own audit passing, a notification
delivery, and the analytics projection after a refresh. The settlement-account
credit is not asserted directly (no account-discovery endpoint; capture moves
suspense to settlement, not the customer balance).
"""

from __future__ import annotations

from decimal import Decimal

from ..evidence import Evidence
from ..models import Payment
from ..ops import trigger_analytics_refresh
from .base import Scenario, World

_AMOUNT = "10.00"
_FUND = "500.00"
_DESTINATION = "sys-v-001-merchant"
_MAX_ATTEMPTS = 25


class SysV001(Scenario):
    id = "sys-v-001"
    title = "Happy-path settlement"
    covers = ["ABS-REQ-001", "ABS-REQ-005"]

    def run(self, world: World, ev: Evidence) -> None:
        cfg = world.config

        # --- health -------------------------------------------------------
        for client in (world.ledger, world.orchestrator, world.risk, world.notification, world.analytics):
            ev.step("health", service=client.service, body=client.health())

        # --- arrange ------------------------------------------------------
        world.ledger.login()
        account_id = world.funded_account("sys-v-001", _FUND)
        ev.step("funded_account", account_id=account_id, funded=_FUND)
        watermark_before = world.analytics.watermark()
        ev.step("analytics_watermark_before", raw_event_count=watermark_before.raw_event_count)

        # --- act: drive a settled payment ---------------------------------
        # POST /payments is stochastic (provider simulator, risk). Retry until one
        # settles. A deterministic provider-outcome seam (M2) will make this a single
        # deterministic call; until then the retry is bounded and recorded.
        settled: Payment | None = None
        balance_before = Decimal("0")
        attempts: list[str] = []
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            balance_before = world.ledger.balance(account_id).balance
            payment = world.orchestrator.create_payment(account_id, _AMOUNT, _DESTINATION)
            attempts.append(payment.state)
            if payment.state == "settled":
                settled = payment
                ev.step(
                    "settled_payment",
                    attempt=attempt,
                    payment_id=payment.id,
                    correlation_id=payment.correlation_id,
                    provider=payment.provider,
                    reserve_tx_id=payment.reserve_tx_id,
                    capture_tx_id=payment.capture_tx_id,
                )
                break
        ev.step("attempt_states", states=attempts)
        ev.require(
            "a payment settled",
            settled is not None,
            f"settled on attempt {len(attempts)} of {_MAX_ATTEMPTS}; states={attempts}"
            if settled is not None
            else f"no settled payment in {_MAX_ATTEMPTS} attempts; states={attempts}",
        )
        assert settled is not None  # for type-checkers; require() already enforced it
        payment_id = settled.id

        # --- assert: customer debit --------------------------------------
        balance_after = world.ledger.balance(account_id).balance
        delta = balance_before - balance_after
        ev.require(
            "customer debited by the payment amount",
            delta == Decimal(_AMOUNT),
            f"balance moved {delta}, expected {_AMOUNT} (before={balance_before}, after={balance_after})",
            covers=["ABS-REQ-001"],
        )

        # --- assert: the deterministic ledger set (reserve + capture) -----
        # A settled payment's deterministic, idempotently keyed set is exactly a
        # reserve and a capture (keys payment:{id}:reserve / :capture), no release.
        # The exhaustive "exactly one per key, stable under retry" proof is SYS-V-003.
        ev.require(
            "settled payment has reserve and capture, no release",
            bool(settled.reserve_tx_id) and bool(settled.capture_tx_id) and settled.release_tx_id is None,
            f"reserve={settled.reserve_tx_id} capture={settled.capture_tx_id} release={settled.release_tx_id}",
            covers=["ABS-REQ-005"],
        )

        # --- assert: ledger audit passes ----------------------------------
        verify = world.ledger.audit_verify()
        ev.step("audit_verify", status=verify.get("status"))
        ev.require(
            "ledger audit/verify passes",
            verify.get("status") == "pass",
            f"audit/verify status={verify.get('status')} discrepancies={verify.get('discrepancies')}",
            covers=["ABS-REQ-001"],
        )

        # --- propagate: drain producer outboxes ---------------------------
        pub = {
            "orchestrator": world.orchestrator.publish_outbox(),
            "risk": world.risk.publish_outbox(),
            "ledger": world.ledger.publish_outbox(),
        }
        ev.step("outbox_drained", **pub)

        # --- assert: a notification was delivered -------------------------
        notifications = world.notification.poll_until(
            fetch=lambda: world.notification.notifications(payment_id),
            predicate=lambda n: any(d.status == "delivered" for d in n.deliveries),
            describe="a delivered notification for the payment",
        )
        delivered = [d for d in notifications.deliveries if d.status == "delivered"]
        ev.step(
            "notifications",
            count=len(notifications.deliveries),
            delivered=len(delivered),
            channels=[d.channel for d in notifications.deliveries],
        )
        ev.require(
            "a notification was delivered for the settled payment",
            len(delivered) >= 1,
            f"deliveries={[(d.channel, d.status) for d in notifications.deliveries]}",
            covers=["ABS-REQ-001"],
        )
        ev.check(
            "notification carries the payment's correlation id",
            any(d.correlation_id == settled.correlation_id for d in notifications.deliveries),
            f"expected correlation_id {settled.correlation_id}",
        )

        # --- assert: analytics reflects the settlement after a refresh ----
        refreshed = trigger_analytics_refresh(cfg)
        ev.step("analytics_refresh", triggered=refreshed)
        account_view = _poll_analytics_account(world, account_id)
        ev.step("analytics_account", account=account_view["account"], watermark=account_view["watermark"])
        ev.require(
            "analytics account projection shows the settled payment",
            int(account_view["account"].get("settled", 0)) >= 1,
            f"account settled={account_view['account'].get('settled')}",
            covers=["ABS-REQ-001"],
        )
        watermark_after = int(account_view["watermark"]["raw_event_count"])
        ev.check(
            "analytics watermark did not regress",
            watermark_after >= watermark_before.raw_event_count,
            f"before={watermark_before.raw_event_count} after={watermark_after}",
        )


def _poll_analytics_account(world: World, account_id: str) -> dict:
    """Poll the per-account projection until it reflects a settled payment."""
    return world.analytics.poll_until(
        fetch=lambda: world.analytics.account(account_id),
        predicate=lambda a: int(a["account"].get("settled", 0)) >= 1,
        describe="analytics account projection to show the settled payment",
    )
