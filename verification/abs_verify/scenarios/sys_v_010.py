"""SYS-V-010: Risk determinism and explainability.

Covers ABS-REQ-014 (a risk decision is deterministic and replayable) and ABS-REQ-015
(every risk decision is explainable).

The same scoring inputs, differing only in `evaluation_id`, must yield an identical
score, band and reason set against a pinned rule version. Explainability is checked
as `score == min(100, sum(reason.weight))`: the score is the fired-rule weights
summed and then capped at 100, so the reasons reconstruct the score through the
documented cap.
"""

from __future__ import annotations

import uuid

from ..evidence import Evidence
from .base import Scenario, World

# Inputs chosen to fire several rules so the reason set is non-trivial:
# HIGH_VALUE (amount >= 5000) + DESTINATION_REPUTATION (watch-listed) + NEW_DESTINATION.
_AMOUNT = "5000.00"
_DESTINATION = "known-fraud-dest"


class SysV010(Scenario):
    id = "sys-v-010"
    title = "Risk determinism and explainability"
    covers = ["ABS-REQ-014", "ABS-REQ-015"]

    def run(self, world: World, ev: Evidence) -> None:
        account_id = str(uuid.uuid4())
        payment_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())

        def body() -> dict:
            return {
                "evaluation_id": str(uuid.uuid4()),  # the only field that differs
                "payment_id": payment_id,
                "account_id": account_id,
                "amount": _AMOUNT,
                "destination": _DESTINATION,
                "correlation_id": correlation_id,
            }

        first = world.risk.evaluate(body())
        second = world.risk.evaluate(body())
        ev.step(
            "evaluations",
            first={"score": first.score, "band": first.band, "decision": first.decision},
            second={"score": second.score, "band": second.band, "decision": second.decision},
            rule_version=first.rule_version,
            rule_config_hash=first.rule_config_hash,
        )

        ev.require(
            "identical inputs yield an identical decision",
            first.decision == second.decision
            and first.band == second.band
            and first.score == second.score,
            f"first=({first.decision},{first.band},{first.score}) "
            f"second=({second.decision},{second.band},{second.score})",
            covers=["ABS-REQ-014"],
        )

        reasons_first = _reason_pairs(first)
        reasons_second = _reason_pairs(second)
        ev.require(
            "identical inputs yield an identical reason set",
            reasons_first == reasons_second,
            f"first={reasons_first} second={reasons_second}",
            covers=["ABS-REQ-014"],
        )

        ev.require(
            "the rule version and config hash are pinned and equal",
            first.rule_version == second.rule_version
            and first.rule_config_hash == second.rule_config_hash,
            f"version {first.rule_version}/{second.rule_version} "
            f"hash {first.rule_config_hash}/{second.rule_config_hash}",
            covers=["ABS-REQ-014"],
        )

        weight_sum = sum(w for _, w in reasons_first)
        expected = min(100, weight_sum)
        ev.require(
            "the reasons reconstruct the score (capped at 100)",
            first.score == expected,
            f"score={first.score} expected min(100, {weight_sum})={expected} reasons={reasons_first}",
            covers=["ABS-REQ-015"],
        )


def _reason_pairs(decision) -> list[tuple[str, int]]:
    """Extract (rule, weight) pairs from a decision's reasons, order preserved."""
    reasons = getattr(decision, "reasons", None)
    if reasons is None:
        reasons = decision.model_dump().get("reasons", [])
    return [(r["rule"], int(r["weight"])) for r in reasons]
