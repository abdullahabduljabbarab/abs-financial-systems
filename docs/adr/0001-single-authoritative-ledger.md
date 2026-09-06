# ADR 0001: A single authoritative ledger owns financial state

## Status

Accepted.

## Context

The platform is a set of services that together move money: a payment orchestrator, a risk engine, notifications, analytics, and the ledger. Any of them could, in principle, hold some notion of balance or write financial records. If more than one service can authoritatively change financial state, the platform has no single source of truth. Balances can disagree, and reconciling them becomes guesswork.

## Decision

Exactly one service, the ledger, may authoritatively mutate financial state. A balance changes only as the result of a double-entry transaction inside the ledger. Every other service either requests a financial operation, decides whether one should occur, consumes events describing what occurred, or presents derived information.

This is recorded as [ABS-REQ-001](../SYSTEM_REQUIREMENTS.md) and enforced by not giving any other service write access to the financial tables.

## Consequences

- There is one place to look for the truth about any balance, and one place to reconcile.
- The orchestrator cannot settle a payment by writing a record itself; it must ask the ledger, which keeps settlement idempotent and auditable.
- Risk can block a payment but cannot change money, which keeps a policy decision separate from a financial one.
- The ledger becomes a dependency for settlement. It is designed for that: it is concurrency-safe, idempotent, and independently reconcilable, and its availability behaviour is a first-class concern for the orchestrator (a payment waits in `SETTLEMENT_PENDING` rather than being lost if the ledger is briefly unavailable).
