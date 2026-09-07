"""SYS-V-004: Duplicate provider callback.

Covers ABS-REQ-003 (duplicate provider callbacks must not duplicate the financial
effect).

A payment is first driven to `unknown` through the controlled provider-outcome seam
(a `verify-outcome:timeout` destination), so it is awaiting a provider outcome. One
success callback is then delivered and replayed N times with the same
`(provider, provider_reference)`. The first is processed and captures; every replay
is a no-op duplicate, and the payment keeps a single, unchanged capture id.
"""

from __future__ import annotations

import uuid

from ..evidence import Evidence
from .base import Scenario, World

_FUND = "500.00"
_AMOUNT = "10.00"
_TIMEOUT_DESTINATION = "verify-outcome:timeout"
_REPLAYS = 3


class SysV004(Scenario):
    id = "sys-v-004"
    title = "Duplicate provider callback"
    covers = ["ABS-REQ-003"]
    requires_provider_hooks = True

    def run(self, world: World, ev: Evidence) -> None:
        world.ledger.login()
        account_id = world.funded_account("sys-v-004", _FUND)

        # Ensure risk allows the payment through to the provider (see SYS-V-005).
        world.warm_risk_feed(ev)

        payment = world.orchestrator.create_payment(account_id, _AMOUNT, _TIMEOUT_DESTINATION)
        ev.step("payment", payment_id=payment.id, state=payment.state, provider=payment.provider)
        ev.require(
            "payment is awaiting a provider outcome (unknown)",
            payment.state == "unknown" and payment.provider is not None,
            f"state={payment.state} provider={payment.provider}",
        )

        # One success callback, then the same body replayed.
        provider = payment.provider
        reference = f"v004-{uuid.uuid4().hex[:12]}"

        first = world.orchestrator.callback(payment.id, provider, reference, "success")
        ev.step("callback_first", result=first)
        ev.require(
            "the first callback is processed",
            first.get("status") == "processed",
            f"status={first.get('status')}",
            covers=["ABS-REQ-003"],
        )

        after_first = world.orchestrator.get_payment(payment.id)
        ev.step("after_first", state=after_first.state, capture_tx_id=after_first.capture_tx_id)
        ev.require(
            "the processed callback settles the payment with a capture",
            after_first.state == "settled" and bool(after_first.capture_tx_id),
            f"state={after_first.state} capture={after_first.capture_tx_id}",
            covers=["ABS-REQ-003"],
        )
        capture_id = after_first.capture_tx_id

        replay_results = []
        for _ in range(_REPLAYS):
            replay_results.append(
                world.orchestrator.callback(payment.id, provider, reference, "success").get("status")
            )
        ev.step("callback_replays", results=replay_results)
        ev.require(
            "every replay of the same callback is a duplicate no-op",
            all(status == "duplicate" for status in replay_results),
            f"replay statuses={replay_results}",
            covers=["ABS-REQ-003"],
        )

        final = world.orchestrator.get_payment(payment.id)
        ev.step("final", state=final.state, capture_tx_id=final.capture_tx_id)
        ev.require(
            "the payment keeps a single, unchanged capture id",
            final.capture_tx_id == capture_id and final.state == "settled",
            f"capture before={capture_id} after={final.capture_tx_id} state={final.state}",
            covers=["ABS-REQ-003"],
        )
