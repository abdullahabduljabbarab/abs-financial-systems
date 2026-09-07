"""The verification matrix: system requirements and the scenarios that prove them.

This mirrors docs/SYSTEM_REQUIREMENTS.md and docs/VERIFICATION_PLAN.md so the portal
can render the requirement-to-scenario coverage. It is static reference data; live
pass/fail evidence is produced by the harness and surfaced separately.
"""

from __future__ import annotations

from typing import Any

REQUIREMENTS: list[dict[str, str]] = [
    {"id": "ABS-REQ-001", "requirement": "Only the ledger may authoritatively mutate financial state."},
    {"id": "ABS-REQ-002", "requirement": "A payment produces its financial effect at most once."},
    {"id": "ABS-REQ-003", "requirement": "Duplicate provider callbacks must not duplicate the financial effect."},
    {"id": "ABS-REQ-004", "requirement": "A provider timeout must not be interpreted as failure."},
    {"id": "ABS-REQ-005", "requirement": "Every payment maps to a deterministic, idempotently keyed set of ledger transactions."},
    {"id": "ABS-REQ-006", "requirement": "Failure of notifications or analytics must not alter financial state."},
    {"id": "ABS-REQ-007", "requirement": "Every published event carries a globally unique event_id."},
    {"id": "ABS-REQ-008", "requirement": "Consumers must tolerate duplicate delivery."},
    {"id": "ABS-REQ-009", "requirement": "Every cross-service operation remains traceable through one correlation_id."},
    {"id": "ABS-REQ-010", "requirement": "Financial reconciliation can independently recover authoritative state from ledger history."},
    {"id": "ABS-REQ-011", "requirement": "A payment's provider is never called unless funds were successfully reserved."},
    {"id": "ABS-REQ-012", "requirement": "An ambiguous provider timeout is pinned to the original provider until reconciliation."},
    {"id": "ABS-REQ-013", "requirement": "Uncertainty in the risk decision must never permit money to move."},
    {"id": "ABS-REQ-014", "requirement": "A risk decision is deterministic and replayable."},
    {"id": "ABS-REQ-015", "requirement": "Every risk decision is explainable."},
    {"id": "ABS-REQ-016", "requirement": "The synchronous decision path is independent of the asynchronous behavioural feed."},
]

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "SYS-V-001", "title": "Happy-path settlement", "covers": ["ABS-REQ-001", "ABS-REQ-005"],
        "assertions": [
            "A payment settles end to end",
            "The customer is debited by exactly the payment amount",
            "The payment carries a reserve and a capture, no release",
            "The ledger audit recomputes state and passes",
            "A notification is delivered carrying the correlation id",
            "Analytics reflects the settled payment after a refresh",
        ],
    },
    {
        "id": "SYS-V-002", "title": "Risk block holds money", "covers": ["ABS-REQ-011", "ABS-REQ-013"],
        "assertions": [
            "A risk-blocked payment ends rejected",
            "No reservation and no provider contact occurred",
            "The account balance is unchanged",
            "The payment never entered reservation",
        ],
    },
    {
        "id": "SYS-V-003", "title": "Financial operation retry safety", "covers": ["ABS-REQ-002", "ABS-REQ-005"],
        "assertions": [
            "Exactly one reserve is keyed to the payment, and no release",
            "The settled payment carries a single capture id",
            "Replaying an idempotency key returns the same transaction",
            "The replayed transaction moves money only once",
        ],
    },
    {
        "id": "SYS-V-004", "title": "Duplicate provider callback", "covers": ["ABS-REQ-003"],
        "assertions": [
            "The payment is awaiting a provider outcome (unknown)",
            "The first callback is processed and settles with a capture",
            "Every replay of the same callback is a duplicate no-op",
            "The payment keeps a single, unchanged capture id",
        ],
    },
    {
        "id": "SYS-V-005", "title": "Provider timeout pins and reconciles", "covers": ["ABS-REQ-004", "ABS-REQ-012"],
        "assertions": [
            "A timed-out payment goes to unknown",
            "The reservation is held: reserved, not captured or released",
            "Funds are held out of the account while unknown",
            "Reconciliation stays on the original provider, no fallback",
            "Reconciliation resolves to a terminal state with the matching ledger movement",
        ],
    },
    {
        "id": "SYS-V-006", "title": "Reservation precedes any provider call", "covers": ["ABS-REQ-011"],
        "assertions": [
            "A payment with a failed reservation ends failed",
            "No provider was contacted and nothing was captured",
            "The balance is unchanged",
            "The payment failed through reservation, never reaching a provider",
        ],
    },
    {
        "id": "SYS-V-007", "title": "Risk service unavailable fails safe to review", "covers": ["ABS-REQ-013"],
        "assertions": [
            "A payment is held for review when risk is unavailable",
            "The held payment took no reservation and no provider contact",
            "The held payment moved no money",
            "Risk is reachable again after restore",
            "The previously held payment remains in review",
        ],
    },
    {
        "id": "SYS-V-008", "title": "Sink failure does not touch money", "covers": ["ABS-REQ-006"],
        "assertions": [
            "A payment settles while the notification sink is down",
            "The customer is debited correctly and the ledger audit passes",
            "The notification subscriptions are severed during the outage",
            "The held notification is delivered once the sink is restored",
            "No channel is double-notified",
        ],
    },
    {
        "id": "SYS-V-009", "title": "Duplicate delivery tolerance", "covers": ["ABS-REQ-008"],
        "assertions": [
            "A duplicate produces no additional notification delivery",
            "The duplicate is recorded once in analytics, not twice",
        ],
    },
    {
        "id": "SYS-V-010", "title": "Risk determinism and explainability", "covers": ["ABS-REQ-014", "ABS-REQ-015"],
        "assertions": [
            "Identical inputs yield an identical decision and reason set",
            "The rule version and config hash are pinned and equal",
            "The reasons reconstruct the score, capped at 100",
        ],
    },
    {
        "id": "SYS-V-011", "title": "Cross-service traceability", "covers": ["ABS-REQ-009"],
        "assertions": [
            "The notification carries the payment's correlation id",
            "Every event in the analytics trace carries the correlation id",
            "The trace spans the payment and the risk decision",
            "Both the orchestrator and the risk engine appear as producers",
        ],
    },
    {
        "id": "SYS-V-012", "title": "Independent ledger and projection integrity", "covers": ["ABS-REQ-010"],
        "assertions": [
            "The ledger audit/verify recomputes state and passes",
            "The ledger hash chain is intact",
            "The analytics watermark does not regress and reads deterministically",
        ],
    },
    {
        "id": "SYS-V-013", "title": "Async risk feed unavailable", "covers": ["ABS-REQ-016"],
        "assertions": [
            "The synchronous decision path returns while the async feed is down",
            "It returns promptly, not blocked on the feed",
            "A further decision is still served with the feed down",
        ],
    },
]

# ABS-REQ-007 is enforced and verified in each producer repository (envelope
# event_id) and observed here only indirectly through the dedup in SYS-V-009.
_INDIRECT = {"ABS-REQ-007": "Verified in each producer repository; observed via dedup (SYS-V-009)."}


def matrix() -> dict[str, Any]:
    by_req: dict[str, list[str]] = {r["id"]: [] for r in REQUIREMENTS}
    for scenario in SCENARIOS:
        for req in scenario["covers"]:
            by_req.setdefault(req, []).append(scenario["id"])
    requirements = [
        {
            **req,
            "scenarios": by_req.get(req["id"], []),
            "note": _INDIRECT.get(req["id"]),
        }
        for req in REQUIREMENTS
    ]
    return {
        "requirements": requirements,
        "scenarios": SCENARIOS,
        "totals": {"requirements": len(REQUIREMENTS), "scenarios": len(SCENARIOS)},
    }
