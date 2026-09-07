"""Compose one payment's cross-service trace.

The trace follows a payment across services using the ids the interfaces actually
expose: the payment's state and lifecycle from the orchestrator, its notification
deliveries, and, through the analytics correlation trace, the risk decision and every
event. The ledger financial effect is presented as the orchestrator's recorded
reserve, capture and release transaction ids, because the ledger transaction does not
carry a correlation id.
"""

from __future__ import annotations

from typing import Any

from .services import Services


async def assemble_trace(services: Services, payment_id: str) -> dict[str, Any] | None:
    payment = await services.payment(payment_id)
    if payment is None:
        return None

    correlation_id = payment.get("correlation_id")
    timeline = await services.payment_events(payment_id)
    deliveries = await services.notifications(payment_id)
    analytics_events = (
        await services.analytics_events(correlation_id) if correlation_id else []
    )

    return {
        "payment": {
            "id": payment.get("id"),
            "account_id": payment.get("account_id"),
            "amount": payment.get("amount"),
            "destination": payment.get("destination"),
            "state": payment.get("state"),
            "provider": payment.get("provider"),
            "correlation_id": correlation_id,
            "created_at": payment.get("created_at"),
        },
        "ledger_effect": {
            "reserve_tx_id": payment.get("reserve_tx_id"),
            "capture_tx_id": payment.get("capture_tx_id"),
            "release_tx_id": payment.get("release_tx_id"),
        },
        "timeline": [
            {
                "from_state": e.get("from_state"),
                "to_state": e.get("to_state"),
                "detail": e.get("detail"),
                "at": e.get("created_at"),
            }
            for e in timeline
        ],
        "notifications": [
            {
                "channel": d.get("channel"),
                "status": d.get("status"),
                "attempt_count": d.get("attempt_count"),
                "destination": d.get("destination"),
                "correlation_id": d.get("correlation_id"),
            }
            for d in deliveries
        ],
        "event_trace": analytics_events,
    }
