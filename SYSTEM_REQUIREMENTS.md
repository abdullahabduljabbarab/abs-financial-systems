# System Requirements

These are the properties that must hold **across** service boundaries. They are the system-of-systems equivalent of the invariants inside the ledger. Each one names the service that owns it and how it is verified. A requirement without a test is a wish, so every requirement here maps to evidence as the owning service is built.

The verification column is filled in as each service ships. "Ledger" entries are already verified in the [ledger-api](https://github.com/abdullahabduljabbarab/ledger-api) repository.

| ID | Requirement | Owner | Verified by |
|----|-------------|-------|-------------|
| ABS-REQ-001 | Only the ledger may authoritatively mutate financial state. | All services | Architecture boundary; no service other than the ledger holds write credentials to financial tables |
| ABS-REQ-002 | A payment settles at most once. | Payment orchestrator | Idempotent settlement keyed on payment id; regression test with repeated settlement attempts |
| ABS-REQ-003 | Duplicate provider callbacks must not duplicate settlement. | Payment orchestrator | Callback dedupe; test replays the same success callback N times and asserts one settlement |
| ABS-REQ-004 | A provider timeout must not be interpreted as failure. | Payment orchestrator | Timeout drives the payment to UNKNOWN; reconciliation resolves it against the provider before any ledger effect |
| ABS-REQ-005 | Every settled payment references exactly one authoritative ledger transaction. | Payment orchestrator | Settlement stores the ledger transaction id; reconciliation asserts a one-to-one mapping |
| ABS-REQ-006 | Failure of notifications or analytics must not alter financial state. | Notification, Analytics | Failure injection: kill each consumer and assert payments still settle and balances are unchanged |
| ABS-REQ-007 | Every published event carries a globally unique `event_id`. | All producers | Envelope validation; the ledger already enforces this and it is verified there |
| ABS-REQ-008 | Consumers must tolerate duplicate delivery. | All consumers | Each consumer deduplicates on `event_id`; unit test for first delivery, redelivery and distinct events |
| ABS-REQ-009 | Every cross-service operation remains traceable through one `correlation_id`. | All services | A single request's `correlation_id` appears on the payment, the risk decision, the ledger transaction and every downstream event |
| ABS-REQ-010 | Financial reconciliation can independently recover authoritative state from ledger history. | Ledger | Reconciliation engine recomputes balances from entries; verified in the ledger repository |

## How these are used

As each service is built, its tests reference the requirement IDs they satisfy, the same way the ledger maps its requirements to named tests. This turns the ecosystem from a set of independently tested services into a system with verifiable end-to-end properties.

The failure-injection requirements (ABS-REQ-003, 004, 006) are the defining ones. They are the difference between a platform that works in the happy path and one that is engineered for the paths that actually break in production.
