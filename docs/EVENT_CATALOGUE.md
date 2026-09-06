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
- Any service that persists state and emits an event about that state produces the event through a local transactional outbox, so the event is written in the same database transaction as the state change and exists if and only if that change committed. This applies to the orchestrator's payment transitions and the risk engine's cases, not only to the ledger's financial state.
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

The orchestrator's events follow the reserve, capture and release lifecycle, so the reservation and its compensation are visible to consumers rather than hidden inside a single "settled".

| Event type | When | Payload |
|------------|------|---------|
| `payment.received` | A payment request was accepted | `payment_id`, `account_id`, `amount`, `destination` |
| `payment.approved` | Risk allowed the payment | `payment_id`, `risk_score` |
| `payment.rejected` | Risk blocked the payment | `payment_id`, `account_id`, `reasons`, `score` |
| `payment.reserved` | Funds were reserved into Payment Suspense | `payment_id`, `reserve_tx_id`, `amount` |
| `payment.reservation_failed` | Reservation failed, provider not called | `payment_id`, `reason` |
| `payment.provider_succeeded` | A provider confirmed success | `payment_id`, `provider`, `provider_ref` |
| `payment.provider_failed` | A provider confirmed failure | `payment_id`, `provider`, `reason` |
| `payment.unknown` | A provider outcome is unresolved; reservation held | `payment_id`, `provider` |
| `payment.captured` | Funds moved from Suspense to Settlement Clearing | `payment_id`, `capture_tx_id` |
| `payment.released` | Reservation compensated back to the customer | `payment_id`, `release_tx_id` |
| `payment.settled` | Payment completed successfully | `payment_id`, `account_id` |
| `payment.failed` | Payment ended unsuccessfully | `payment_id`, `account_id`, `reason` |

### Risk Engine

| Event type | When | Payload |
|------------|------|---------|
| `risk.evaluated` | A risk decision was made | `payment_id`, `account_id`, `decision`, `score`, `reasons` |

### Notification Service

The notification service is a strict sink: it consumes `payment-events` and `risk-events` and produces customer-facing messages. It publishes no events and has no outbound broker path, by design (its isolation is the point, ABS-REQ-006). Its delivery records are exposed over a read API, not as events. It therefore has no entry in this catalogue as a producer.

Customer-facing events it acts on must carry `account_id`, so it can determine the recipient from the event alone without ever calling back upstream. That is why `payment.settled`, `payment.failed` and `payment.rejected` carry `account_id` above.

### Analytics Service

The analytics service is also a strict sink. It consumes all three event topics (`transaction-events`, `payment-events`, `risk-events`) into a durable raw-event history and materialises read projections over it. Like the notification service it publishes no events and has no outbound broker path (ABS-REQ-006); its projections are exposed over a read API. It therefore has no entry in this catalogue as a producer.

## Topics

Events are grouped onto Pub/Sub topics by aggregate:

- `transaction-events` (ledger)
- `payment-events` (orchestrator)
- `risk-events` (risk engine)

There is deliberately no notification topic: the notification service is a strict
sink and publishes nothing (ABS-REQ-006). Each topic has a paired dead-letter
topic owned by the consumer that dead-letters onto it.

Consumers subscribe to the topics they care about and filter by `event_type` within them.
