# System Requirements

These are the properties that must hold **across** service boundaries. They are the system-of-systems equivalent of the invariants inside the ledger. Each one names the service that owns it and how it is verified. A requirement without a test is a wish, so every requirement here maps to evidence as the owning service is built.

The verification column is filled in as each service ships. "Ledger" entries are already verified in the [ledger-api](https://github.com/abdullahabduljabbarab/ledger-api) repository.

| ID | Requirement | Owner | Verified by |
|----|-------------|-------|-------------|
| ABS-REQ-001 | Only the ledger may authoritatively mutate financial state. | All services | Architecture boundary; no service other than the ledger holds write credentials to financial tables |
| ABS-REQ-002 | A payment produces its financial effect at most once. | Payment orchestrator | Idempotent reserve, capture and release keyed on payment id; regression test replays each step and asserts no duplicate ledger movement |
| ABS-REQ-003 | Duplicate provider callbacks must not duplicate the financial effect. | Payment orchestrator | Callback dedupe; test replays the same success callback N times and asserts one capture |
| ABS-REQ-004 | A provider timeout must not be interpreted as failure. | Payment orchestrator | Timeout drives the payment to UNKNOWN and holds the reservation; reconciliation resolves it against the provider before capture or release |
| ABS-REQ-005 | Every payment maps to a deterministic, idempotently keyed set of ledger transactions (reserve, then capture or release); retries never add to the set. | Payment orchestrator | Operations keyed `payment:{id}:reserve/capture/release`; test asserts the transaction set is stable under retry |
| ABS-REQ-006 | Failure of notifications or analytics must not alter financial state. | Notification, Analytics | Failure injection: kill each consumer and assert payments still settle and balances are unchanged |
| ABS-REQ-007 | Every published event carries a globally unique `event_id`. | All producers | Envelope validation; the ledger already enforces this and it is verified there |
| ABS-REQ-008 | Consumers must tolerate duplicate delivery. | All consumers | Each consumer deduplicates on `event_id`; unit test for first delivery, redelivery and distinct events |
| ABS-REQ-009 | Every cross-service operation remains traceable through one `correlation_id`. | All services | A single request's `correlation_id` appears on the payment, the risk decision, and every downstream notification and analytics event. The ledger transaction does not carry the `correlation_id`; the payment's financial effect is traced to the ledger through the orchestrator's recorded reserve, capture and release transaction ids. |
| ABS-REQ-010 | Financial reconciliation can independently recover authoritative state from ledger history. | Ledger | Reconciliation engine recomputes balances from entries; verified in the ledger repository |
| ABS-REQ-011 | A payment's provider is never called unless funds were successfully reserved. | Payment orchestrator | Reservation runs before any provider call; test asserts a failed reservation ends the payment as FAILED with no provider contact |
| ABS-REQ-012 | A payment with an ambiguous provider timeout is never routed to another provider; it is pinned to the original until reconciliation resolves it. | Payment orchestrator | Test asserts a timeout drives UNKNOWN and no fallback occurs before reconciliation; fallback is allowed only after a definitive failure |
| ABS-REQ-013 | Uncertainty in the risk decision must never permit money to move. If the risk engine is unavailable or times out, the payment is held for review, never allowed and never automatically rejected. | Risk engine, Payment orchestrator | Failure injection: with the risk engine unreachable, a payment is driven to RISK_REVIEW; test asserts no reservation or provider contact, and the payment is neither allowed nor auto-rejected |
| ABS-REQ-014 | A risk decision is deterministic and replayable: the same input snapshot and rule version always yield the same score and decision. | Risk engine | Test evaluates a fixed input against a pinned rule version and asserts a stable score, band and reason set |
| ABS-REQ-015 | Every risk decision is explainable: it records the input snapshot, the rule version, each triggered rule with its weight, the total score, and the decision band. | Risk engine | The persisted decision and the API response carry the triggered rules and weights; test asserts the reasons reconstruct the score |
| ABS-REQ-016 | The synchronous decision path is independent of the asynchronous behavioural-state path, so lag or failure in event consumption cannot block or change a decision already returned. | Risk engine | The decision is computed from the snapshot at evaluate time; test asserts a decision is returned with the event consumer stopped |

## How these are used

As each service is built, its tests reference the requirement IDs they satisfy, the same way the ledger maps its requirements to named tests. This turns the ecosystem from a set of independently tested services into a system with verifiable end-to-end properties.

The failure-injection requirements (ABS-REQ-003, 004, 006, 013) are the defining ones. They are the difference between a platform that works in the happy path and one that is engineered for the paths that actually break in production. ABS-REQ-013 is the risk equivalent of the orchestrator's reservation rule: uncertainty in a decision service must fail towards holding a payment, never towards moving money.
