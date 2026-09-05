# Event Catalogue

Every service in the platform speaks one event language. This document defines the envelope that wraps every event and catalogues the events each service produces. It is the contract that lets services be built independently and still fit together.

## The envelope

Every event, from every producer, has this shape:

```json
{
  "event_id": "uuid",
  "event_type": "payment.succeeded",
  "event_version": 1,
  "occurred_at": "2026-09-05T12:00:00Z",
  "producer": "payment-orchestrator",
  "correlation_id": "uuid",
  "causation_id": "uuid",
  "aggregate_id": "payment-uuid",
  "payload": {}
}
```

| Field | Meaning |
|-------|---------|
| `event_id` | Globally unique id for this event. Consumers deduplicate on it (ABS-REQ-007, ABS-REQ-008). |
| `event_type` | Dotted name, `<aggregate>.<past-tense-fact>`. Events describe things that already happened. |
| `event_version` | Schema version of the payload for this `event_type`. Incremented on breaking payload changes. |
| `occurred_at` | UTC timestamp of when the fact occurred, not when it was published. |
| `producer` | The service that emitted the event. |
| `correlation_id` | The originating user action. The same value threads through every event caused by one request (ABS-REQ-009). |
| `causation_id` | The `event_id` or request id that directly caused this event. Lets a causal chain be reconstructed. |
| `aggregate_id` | The id of the entity this event is about (a payment id, a transaction id). |
| `payload` | Event-type-specific body, versioned by `event_version`. |

### Rules

- Events are facts in the past tense. A producer never publishes an intention, only an outcome.
- Delivery is at-least-once. Every consumer must be safe to run on a duplicate, and deduplicates on `event_id`.
- Where financial state is involved, events are produced through the transactional outbox, so the event exists if and only if the state change committed.
- Payload changes that are not backward compatible increment `event_version`; consumers handle the versions they understand.

## Catalogue

### Ledger API

The ledger currently emits a subset of the envelope (`event_id`, `event_type`, and a transaction payload). Bringing it up to the full envelope, in particular carrying `correlation_id` end to end, is the first integration task when the orchestrator is wired in.

| Event type | When | Payload |
|------------|------|---------|
| `transaction.deposit` | A deposit committed | `transaction_id`, `amount`, `idempotency_key`, `reference` |
| `transaction.withdrawal` | A withdrawal committed | `transaction_id`, `amount`, `idempotency_key`, `reference` |
| `transaction.transfer` | A transfer committed | `transaction_id`, `amount`, `from_account_id`, `to_account_id`, `reference` |

### Payment Orchestrator

| Event type | When | Payload |
|------------|------|---------|
| `payment.received` | A payment request was accepted | `payment_id`, `account_id`, `amount`, `destination` |
| `payment.approved` | Risk allowed the payment | `payment_id`, `risk_score` |
| `payment.rejected` | Risk blocked the payment | `payment_id`, `reasons` |
| `payment.succeeded` | A provider confirmed success | `payment_id`, `provider`, `provider_ref` |
| `payment.failed` | A provider confirmed failure | `payment_id`, `provider`, `reason` |
| `payment.unknown` | A provider outcome is unresolved | `payment_id`, `provider` |
| `payment.settled` | The payment was settled in the ledger | `payment_id`, `ledger_transaction_id` |

### Risk Engine

| Event type | When | Payload |
|------------|------|---------|
| `risk.evaluated` | A risk decision was made | `payment_id`, `decision`, `score`, `reasons` |
| `risk.alert.created` | A risk case was opened for review | `case_id`, `account_id`, `reasons` |

### Notification Service

| Event type | When | Payload |
|------------|------|---------|
| `notification.sent` | A notification was delivered | `notification_id`, `channel`, `destination` |
| `notification.failed` | Delivery failed after retries | `notification_id`, `channel`, `reason` |

## Topics

Events are grouped onto Pub/Sub topics by aggregate:

- `transaction-events` (ledger)
- `payment-events` (orchestrator)
- `risk-events` (risk engine)
- `notification-events` (notifications)

Consumers subscribe to the topics they care about and filter by `event_type` within them.
