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
    {"id": "SYS-V-001", "title": "Happy-path settlement", "covers": ["ABS-REQ-001", "ABS-REQ-005"]},
    {"id": "SYS-V-002", "title": "Risk block holds money", "covers": ["ABS-REQ-011", "ABS-REQ-013"]},
    {"id": "SYS-V-003", "title": "Financial operation retry safety", "covers": ["ABS-REQ-002", "ABS-REQ-005"]},
    {"id": "SYS-V-004", "title": "Duplicate provider callback", "covers": ["ABS-REQ-003"]},
    {"id": "SYS-V-005", "title": "Provider timeout pins and reconciles", "covers": ["ABS-REQ-004", "ABS-REQ-012"]},
    {"id": "SYS-V-006", "title": "Reservation precedes any provider call", "covers": ["ABS-REQ-011"]},
    {"id": "SYS-V-007", "title": "Risk service unavailable fails safe to review", "covers": ["ABS-REQ-013"]},
    {"id": "SYS-V-008", "title": "Sink failure does not touch money", "covers": ["ABS-REQ-006"]},
    {"id": "SYS-V-009", "title": "Duplicate delivery tolerance", "covers": ["ABS-REQ-008"]},
    {"id": "SYS-V-010", "title": "Risk determinism and explainability", "covers": ["ABS-REQ-014", "ABS-REQ-015"]},
    {"id": "SYS-V-011", "title": "Cross-service traceability", "covers": ["ABS-REQ-009"]},
    {"id": "SYS-V-012", "title": "Independent ledger and projection integrity", "covers": ["ABS-REQ-010"]},
    {"id": "SYS-V-013", "title": "Async risk feed unavailable", "covers": ["ABS-REQ-016"]},
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
