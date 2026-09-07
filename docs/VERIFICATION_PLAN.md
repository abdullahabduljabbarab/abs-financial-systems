# System Verification Plan

Each ABS service is tested in its own repository. This plan is the layer above:
it verifies the properties that only exist **between** services, by driving the
real, live services as black boxes through the HTTP surface in
[SERVICE_CATALOGUE.md](SERVICE_CATALOGUE.md) and asserting on their responses and
on the events observed through consumers' read APIs. It never reaches inside a
service.

Every scenario maps to one or more requirements in
[SYSTEM_REQUIREMENTS.md](SYSTEM_REQUIREMENTS.md) and produces immutable per-run
evidence. The scenarios are designed against what the interfaces actually expose,
not what would be convenient: there is no payment-list endpoint, payment creation
is not idempotent, analytics has no status endpoint, and the ledger transaction
carries no correlation id. The plan works within those facts.

## How a scenario runs

1. **Arrange.** Obtain a ledger admin token (`POST /auth/token`). Create and fund
   a fresh account so the run is self-contained and repeatable.
2. **Act.** Drive the flow through the public endpoints, capturing every id the
   responses return (payment id, correlation id, reserve/capture/release tx ids,
   evaluation id, event ids).
3. **Propagate.** Where the assertion depends on a consumer seeing an event, drain
   the relevant producer's outbox (`POST /outbox/publish`) and poll the consumer's
   read API with a bounded wait.
4. **Assert.** Check the invariant, not an incidental value. Prefer balance
   conservation, at-most-once effect, presence of a downstream record, and
   determinism over a fixed terminal state.
5. **Record.** Write an immutable evidence record for the run (inputs, captured
   ids, responses, pass/fail per assertion, timestamps) keyed to the SYS-V id and
   the ABS-REQ ids it covers.

**Controlled failure injection.** The failure-mode scenarios need a fault the
happy path will not produce on demand. Faults are injected by controlled operator
tooling (a harness CLI acting on the deployment: stopping a consumer revision,
pointing the orchestrator at an unreachable risk URL, driving a deterministic
provider outcome through `/callback`), never by a public "break yourself" endpoint
on any service. Each such scenario names its injection method below.

## Scenarios

### SYS-V-001 Happy-path settlement
**Covers:** ABS-REQ-001, ABS-REQ-005.
A funded payment settles end to end. Create the payment; drive it to `settled` (or
force the settle edge with a `success` `/callback` on a prepared payment). Assert:
the **customer** account balance fell by exactly the amount, the payment carries a
`reserve_tx_id` and a `capture_tx_id` and no `release_tx_id`, and `GET /audit/verify`
returns `pass`. After draining outboxes, assert a notification delivery exists for
the payment and, after a refresh, analytics reflects one more settled payment
(checked against the watermark). The settlement account credit is not asserted
directly: there is no account-discovery endpoint, and capture moves suspense to
settlement rather than the customer balance, so the customer debit plus the capture
tx id plus `audit/verify` passing is the proof. (If the harness is given the fixed
suspense and settlement system-account ids from the orchestrator's configuration,
it may additionally assert the settlement credit, but the scenario does not depend
on it.)

### SYS-V-002 Risk block holds money
**Covers:** ABS-REQ-011, ABS-REQ-013.
A payment that risk blocks ends `rejected` with no financial effect. Drive an
evaluation to a `block` decision; assert the payment reaches `rejected`, has no
`reserve_tx_id`, the account balance is unchanged, and no provider was contacted.

### SYS-V-003 Financial operation retry safety
**Covers:** ABS-REQ-002, ABS-REQ-005.
Not a duplicate-HTTP-request test: `POST /payments` is deliberately not idempotent.
This proves the at-most-once property at the level where it actually holds, the
ledger effect. For one settled payment, assert (via `GET /transactions` filtered to
the account) that exactly one ledger transaction exists with the deterministic
`payment:{id}:reserve` idempotency key and exactly one with `payment:{id}:capture`
(or `payment:{id}:release` for a failed payment). Corroborate ledger idempotency
directly: replay a `POST /transactions` with an already-used `idempotency_key` and
assert the same transaction is returned, not a second one (and the balance does not
move twice).

### SYS-V-004 Duplicate provider callback
**Covers:** ABS-REQ-003.
Prepare a payment in `unknown` (see SYS-V-005's injection), then call
`POST /payments/{id}/callback` once with a `success` outcome and a fixed
`(provider, provider_reference)`, and replay that exact same body N times. Assert
the first returns `processed` and every replay returns `duplicate`, and, as the
financial proof, that exactly one ledger transaction with the deterministic
`payment:{id}:capture` idempotency key exists (counted through `GET /transactions`).
Do not use the customer balance as the proof of a single capture: capture moves
suspense to settlement, not the customer account.

### SYS-V-005 Provider timeout pins and reconciles
**Covers:** ABS-REQ-004, ABS-REQ-012.
A provider `timeout` is a synchronous provider result that drives the payment to
`unknown` at creation time; it is not a callback. Because the providers are
stochastic simulators, the timeout is produced by controlled operator tooling that
forces the simulator's next outcome to `timeout` (the preferred, deterministic V&V
path); if the deployed orchestrator exposes no such control, the harness falls back
to creating payments until one naturally reaches `unknown` (bounded). Assert the
payment is `unknown` with the reservation still held (no capture, no release), it is
pinned to its original provider with no fallback, and `POST /payments/{id}/reconcile`
then resolves it against that same provider to a terminal state with the matching
ledger movement. (A deterministic provider-outcome control is a small, test-only
operator seam; if V&V determinism requires it and it does not exist, it is proposed
as the smallest addition, not worked around by reading internals.)

### SYS-V-006 Reservation precedes any provider call
**Covers:** ABS-REQ-011.
A payment whose reservation cannot succeed ends `failed` with no provider contact.
Inject a reservation failure (a payment against an account with insufficient funds
to reserve). Assert the payment ends `failed` (via `reservation_failed`), there is
no provider assigned and no `capture_tx_id`, and the balance is unchanged.

### SYS-V-007 Risk service unavailable fails safe to review
**Covers:** ABS-REQ-013.
With the risk engine unreachable to the orchestrator (controlled injection:
orchestrator pointed at a dead risk URL, or the risk revision made unreachable),
create a payment. Assert it is driven to `risk_review` and held: no reservation, no
provider contact, and it is neither allowed nor auto-rejected. Then restore risk and
assert a **new** payment receives a normal risk decision. The already-held payment
stays held: the orchestrator exposes no public operation to approve or re-drive a
`risk_review` payment, and the scenario does not invent one.

### SYS-V-008 Sink failure does not touch money
**Covers:** ABS-REQ-006.
Interrupt delivery to a consumer without pretending Cloud Run scaling is downtime
(a scaled-to-zero service simply cold-starts on the next push). Controlled
injection: temporarily revoke the Pub/Sub push identity's invoker permission on the
sink, or point its subscription at a failing endpoint; Pub/Sub then holds and
retries the backlog. Run a payment to `settled` with the sink cut off and assert the
payment still settles and balances are correct. Restore delivery and assert the
backlog drains with no double effect: the notification appears, and for analytics,
after delivery resumes **and the refresh job runs**, the projections catch up
(refresh is off the ingest path, so ingest alone does not advance projections).

### SYS-V-009 Duplicate delivery tolerance
**Covers:** ABS-REQ-008.
Cause the same event to be delivered twice to a consumer (drain is at-least-once, or
re-post an identical envelope to a consumer's `/events/pubsub`). Assert the
consumer's read API shows the effect exactly once: one notification delivery per
`(event_id, channel)`, and the analytics ingest returns `recorded` then `duplicate`
with the event count and projections unchanged on the redelivery.

### SYS-V-010 Risk determinism and explainability
**Covers:** ABS-REQ-014, ABS-REQ-015.
Evaluate the same scoring inputs twice, identical in every field except the
`evaluation_id` (the idempotency key must differ to force a fresh evaluation),
against a pinned `rule_version`. Assert identical `score`, `band` and `reasons`, and
matching `rule_version` and `rule_config_hash`. For explainability, assert
`score == min(100, sum(reason.weight))`: the score is the fired-rule weights summed
and then capped at 100, so the reasons reconstruct the score through the documented
cap, not as a raw sum.

### SYS-V-011 Cross-service traceability
**Covers:** ABS-REQ-009.
For one settled payment, take its `correlation_id` and assert the same value appears
on the downstream notification delivery (`GET /notifications/{payment_id}`) and, in
the analytics correlation trace (`GET /analytics/events?correlation_id={id}`), on
every ingested event. The analytics trace closes the risk and analytics legs
together: it includes the `risk.evaluated` event, which the orchestrator emits with
the payment's `correlation_id`, so the id is shown to thread through risk and
analytics without needing a separate risk-decision lookup. Assert the trace spans
the payment and the risk decision and names both the orchestrator and the risk
engine as producers. The ledger financial effect is reached through the
orchestrator's recorded `reserve_tx_id` / `capture_tx_id` (the ledger transaction is
keyed by idempotency key, not correlation id), so the trace is complete without
inventing a ledger correlation field.
**Interface addition.** The analytics correlation trace endpoint,
`GET /analytics/events?correlation_id={id}`, was the one genuine observability gap
found in discovery. It was added as the smallest domain-correct fix: read-only,
trace metadata only (no payload), reading raw history. It also backs the portal's
payment trace.

### SYS-V-012 Independent ledger and projection integrity
**Covers:** ABS-REQ-010, and analytics rebuild determinism.
Assert the ledger's own recovery guarantees hold from outside: `GET /audit/verify`
returns `pass` (balances recomputed from history, invariants intact) and
`GET /audit/chain` returns `pass` (hash chain unbroken). Assert analytics
projections are a deterministic function of raw history: `raw_event_count` never
regresses across an ingest-then-refresh cycle (ingest writes raw events; the
projection watermark advances only after the refresh job runs), and a rebuild
reproduces the same projection content at the same `{raw_event_count, as_of}`.
Rebuild is exercised through the operational Cloud Run Job and observed via the read
API and watermark, never an HTTP mutation.

### SYS-V-013 Async risk feed unavailable
**Covers:** ABS-REQ-016.
Distinct from SYS-V-007 (which fails the risk service to the orchestrator): this
fails the risk engine's own asynchronous behavioural feed while its synchronous
decision path stays up. Controlled injection: interrupt `payment-events` delivery to
the risk engine's `/events/pubsub` (revoke its push identity or fail its
subscription endpoint) so the behavioural state goes stale. Then call
`POST /risk/evaluate` directly and assert a synchronous decision still returns, and
that the stale-state policy applies where appropriate (a decision that would
otherwise `allow` is floored to `review` when state is stale). This proves the
synchronous path is independent of async feed freshness.

## Coverage

| ABS-REQ | Covered by |
|---|---|
| ABS-REQ-001 | SYS-V-001 |
| ABS-REQ-002 | SYS-V-003 |
| ABS-REQ-003 | SYS-V-004 |
| ABS-REQ-004 | SYS-V-005 |
| ABS-REQ-005 | SYS-V-001, SYS-V-003 |
| ABS-REQ-006 | SYS-V-008 |
| ABS-REQ-007 | Enforced and verified in each producer repository (envelope `event_id`); observed here indirectly through dedup in SYS-V-009 |
| ABS-REQ-008 | SYS-V-009 |
| ABS-REQ-009 | SYS-V-011 (payment, notification, and risk plus analytics via the correlation trace) |
| ABS-REQ-010 | SYS-V-012 |
| ABS-REQ-011 | SYS-V-002, SYS-V-006 |
| ABS-REQ-012 | SYS-V-005 |
| ABS-REQ-013 | SYS-V-002, SYS-V-007 |
| ABS-REQ-014 | SYS-V-010 |
| ABS-REQ-015 | SYS-V-010 |
| ABS-REQ-016 | SYS-V-013 |

## What this plan deliberately does not do

- It does not query a payment-list endpoint; none exists, and the harness keys on
  ids it captured during the run.
- It does not assert that `POST /payments` is idempotent; it proves at-most-once at
  the ledger-effect and callback-dedup level instead.
- It does not read any analytics `/status` endpoint; freshness comes from the
  watermark embedded in every projection response.
- It does not invent an operation to resume a payment held in `risk_review`; no such
  public operation exists.
- It does not treat Cloud Run scale-to-zero as downtime; it interrupts delivery at
  the Pub/Sub layer instead.
- It does not read any service's database or queue to close an observability gap.
  The one gap discovery found, correlation continuity into analytics, was closed by
  adding a read-only, metadata-only trace endpoint to analytics, the smallest
  domain-correct fix, rather than by reaching inside the store.
