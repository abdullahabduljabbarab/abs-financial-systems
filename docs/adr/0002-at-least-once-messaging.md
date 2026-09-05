# ADR 0002: At-least-once messaging with consumer deduplication

## Status

Accepted.

## Context

Services communicate through Pub/Sub. A broker can deliver the same message more than once, and a producer that crashes between publishing and recording that it published will publish again on recovery. The platform has to choose what delivery guarantee it relies on and where duplicates are handled.

Exactly-once delivery across a network is not something a broker can honestly provide. Pretending to have it pushes the hard case into the corners where it is least expected.

## Decision

Delivery is at-least-once, stated plainly. Every event carries a globally unique `event_id`, and every consumer deduplicates on it before acting. Where an event describes a committed financial change, it is produced through the transactional outbox pattern, so the event exists if and only if the change committed.

This is recorded as [ABS-REQ-007](../../SYSTEM_REQUIREMENTS.md) and [ABS-REQ-008](../../SYSTEM_REQUIREMENTS.md).

## Consequences

- Consumers are simpler to reason about: they must be idempotent, and that single property covers redelivery, replay and producer retries.
- The failure modes are honest. A notification may be attempted twice; deduplication makes that harmless rather than hidden.
- The outbox couples event production to the database transaction, so there is no window where money moves without an event, or an event fires without the money moving.
- Downstream services can be restarted, redeployed or backfilled by replaying a topic, because duplicate delivery is already a handled case rather than a corruption risk.
