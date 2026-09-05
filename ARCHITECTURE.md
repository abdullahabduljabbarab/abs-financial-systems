# Architecture

## The one rule

The ledger is the single authoritative owner of financial state. Every other service falls into one of four roles:

- **Requests** a financial operation (the payment orchestrator asks the ledger to settle).
- **Decides** whether an operation should happen (the risk engine allows or blocks).
- **Consumes** events describing what happened (notifications, analytics, risk state).
- **Presents** derived information (the portal).

No service other than the ledger writes to financial state. A balance changes only as the result of a double-entry transaction inside the ledger. This is enforced as [ABS-REQ-001](SYSTEM_REQUIREMENTS.md).

## Layers

```
                         Client / Ops Portal
                                 |
              -------------------------------------------
              |                  |                      |
         Account APIs       Payment API             Risk APIs
                                 |
                        Payment Orchestrator
                     routing, state machine, retries,
                     circuit breakers, reconciliation
                          |                 |
                    Risk Engine        Provider simulators
                          |
                       Ledger API
                 authoritative financial state
                                 |
                              Pub/Sub
              -------------------------------------------
              |                  |                      |
        Notifications         Analytics            Risk cases
```

The orchestrator sits between a payment request and settlement. It is the only service that talks to external providers, and it is the only service that asks the ledger to settle a payment. Risk sits to the side of the orchestrator: it can change the decision, but it cannot change the money.

## Payment lifecycle, end to end

A single payment moves through the platform like this, with one `correlation_id` threaded through every hop:

```
HTTP request            -> payment created, correlation_id assigned
Risk evaluation         -> allow / review / block
Provider request        -> success / failed / timeout (unknown)
Ledger settlement       -> exactly one double-entry transaction
Outbox event            -> written in the same transaction as the entries
Pub/Sub                 -> at-least-once delivery
Notification            -> side effect, may fail independently
Analytics               -> read model updated
```

The interesting states are the ambiguous ones. A provider **timeout** does not mean the payment failed; it means the outcome is unknown and must be reconciled before any financial effect is applied. Blindly retrying an unknown could settle the same payment twice, so the orchestrator resolves the ambiguity against the provider before touching the ledger. This is [ABS-REQ-004](SYSTEM_REQUIREMENTS.md).

## Data ownership

Each service owns its own database. Nothing reaches across into another service's tables.

- **Ledger** owns accounts, transactions and ledger entries. It is the source of truth for balances, which are derived from entries and never stored.
- **Payment orchestrator** owns payment records and their state history.
- **Risk engine** owns risk cases and the rolling state it builds from transaction events.
- **Notification service** owns a delivery log.
- **Analytics** owns a read model in BigQuery, populated only from events. It never writes back into the financial core.

At portfolio scale this is one managed PostgreSQL instance with logically separate databases, plus BigQuery for analytics. Service ownership boundaries are preserved without paying for four separate instances.

## Messaging

Services communicate through Pub/Sub using the shared envelope in [EVENT_CATALOGUE.md](EVENT_CATALOGUE.md). Delivery is **at-least-once**: the same event can arrive more than once, so every consumer deduplicates on `event_id`. Events are produced through the transactional outbox pattern where financial state is involved, so an event exists if and only if the state change that it describes committed.

## Traceability

Every event carries a `correlation_id` (the identifier for the originating user action) and a `causation_id` (the event or request that directly caused this one). Together they let a single payment be followed from the inbound HTTP request through risk, the provider, the ledger transaction, the outbox event, and every downstream consumer. The ecosystem portal surfaces this as a live end-to-end trace.

## Deployment

All services run on Cloud Run in `europe-west2`. Cloud SQL holds the transactional databases, Pub/Sub is the event bus, BigQuery holds the analytics read model, Secret Manager holds credentials, and Artifact Registry holds the images. The infrastructure is defined as code in the `platform-infrastructure` repository and validated in CI. CI/CD lints, tests, validates the Terraform and deploys on green.
