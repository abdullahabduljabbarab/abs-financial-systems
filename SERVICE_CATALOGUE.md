# Service Catalogue

The external HTTP surface of every ABS service, as the rest of the platform is
allowed to see it. This is the black-box contract: what each service exposes, how
it is authenticated, and what it produces and consumes. It is derived from the
services' own code, not aspirational, and it is the single source the system
verification harness and the engineering portal build against.

The rule that makes this a contract: nothing here reaches inside a service. No
database, no queue internals, no private helper. A service is its HTTP API and the
events it publishes, nothing more. If a fact is not observable through this
surface, it is not in this catalogue.

## Conventions

- **Base URLs.** Each service is a Cloud Run service in project `ledger-api-507618`,
  region `europe-west2`, reachable at `https://<service>-eppidgbmxa-nw.a.run.app`.
  The live hosts are listed per service below.
- **Event envelope.** Every published event uses the ABS envelope defined in
  [EVENT_CATALOGUE.md](EVENT_CATALOGUE.md); this catalogue does not repeat it.
- **The outbox relay is manual.** Each producer writes events to a transactional
  outbox and relays them to Pub/Sub only when `POST /outbox/publish` is called
  (oldest-first, capped by `limit`, stops at the first failure to preserve order).
  A verifier that wants an event to reach its consumers must drain the producer's
  outbox itself. Delivery to consumers is then at-least-once.
- **Health.** Every service exposes `GET /health` returning `200` with a small
  JSON body. The shape differs by service and is given below.
- **Authentication posture.** Only the ledger authenticates its business API (JWT,
  role-based). The orchestrator, and the read surfaces of risk, notification and
  analytics, are deployed `--allow-unauthenticated` and require no caller identity.
  The one authenticated non-ledger path everywhere is `POST /events/pubsub`, which
  requires a Google OIDC push token minted for that service's push identity; it is
  the Pub/Sub-to-service ingress, not a caller-facing API.

## Authentication summary

| Service | Business API auth | `/events/pubsub` auth |
|---|---|---|
| ledger-api | Bearer JWT, role-based (admin / auditor / customer) | (no such endpoint) |
| payment-orchestrator | none (public) | (no such endpoint) |
| risk-engine | none (public) | Google OIDC push token |
| notification-service | none (public) | Google OIDC push token |
| analytics-service | none (public) | Google OIDC push token |

---

## Ledger API

The authoritative double-entry ledger. The only service that may mutate financial
state (ABS-REQ-001). Append-only, idempotent, hash-chained.

- **Live:** `https://ledger-api-eppidgbmxa-nw.a.run.app`
- **Auth:** Bearer JWT (HS256, 60-minute expiry) carrying `sub` and `role`. Obtain
  one from `POST /auth/token`. Roles: `admin`, `auditor`, `customer`. A call
  outside a route's allowed roles returns `403`; a missing or invalid token, `401`.
- **Health:** `{ "status": "ok", "database": "connected", "db_latency_ms": <float> }`

| Method + path | Auth (role) | Purpose |
|---|---|---|
| `GET /health` | none | Liveness + DB probe |
| `GET /status` | none | Public counts summary (accounts, transactions, entries, outbox pending) |
| `POST /auth/token` | none | Exchange username/password (form body) for a bearer JWT |
| `POST /accounts` | admin | Create an account (`name`) |
| `GET /accounts/{id}` | any authed | Retrieve an account |
| `GET /accounts/{id}/balance` | any authed | Derived balance (summed from entries) |
| `GET /accounts/{id}/entries` | any authed | Ledger entries, cursor-paginated |
| `GET /accounts/{id}/statement` | any authed | Statement with running balance over a date range |
| `POST /transactions` | admin / customer | Record deposit / withdrawal / transfer; idempotent, emits an event |
| `GET /transactions` | any authed | List transactions, cursor-paginated, filterable |
| `GET /outbox/pending` | admin | Inspect unpublished outbox events |
| `POST /outbox/publish` | admin | Relay pending events to the broker |
| `GET /audit/verify` | auditor / admin | Recompute balances and verify ledger invariants |
| `GET /audit/chain` | auditor / admin | Verify the SHA-256 tamper-evident hash chain |

**Key request shapes.**
- `POST /transactions` (`TransactionCreate`): `idempotency_key` (str), `type`
  (`deposit`|`withdrawal`|`transfer`), `amount` (Decimal > 0, 2dp), `account_id`
  (UUID, required for deposit/withdrawal), `from_account_id` / `to_account_id`
  (UUID, both required for transfer, must differ), `reference` (str, optional).
  Reused key with different params: `409`. Insufficient balance / bad account
  fields: `422`.
- `POST /accounts` (`AccountCreate`): `name` (str, 1-255). Duplicate name: `409`.

**Pagination.** Cursor-based on `/transactions` and `/accounts/{id}/entries`
(`limit` default 20, max 100, opaque `next_cursor`). Outbox endpoints use `limit`
default 50, max 200. No `offset` anywhere.

**Produces:** `transaction.deposit`, `transaction.withdrawal`, `transaction.transfer`
(pattern `transaction.{type}`) onto **`transaction-events`**. Payload: `transaction_id`,
`type`, `amount`, `idempotency_key`, `reference`. Pub/Sub attributes carry `event_id`
and `event_type`.
**Consumes:** nothing.

Default seed users exist in code for a self-contained demo (`admin` / `auditor` /
`customer`); the admin credential is what the orchestrator authenticates with.

---

## Payment Orchestrator

The payment lifecycle. Drives a payment through risk, reservation, provider and
capture-or-release as a saga, and is the compensation authority (ABS-REQ-002,
ABS-REQ-005). Holds no money itself; every movement is a ledger call.

- **Live:** `https://payment-orchestrator-eppidgbmxa-nw.a.run.app`
- **Auth:** none. Every endpoint is public.
- **Health:** `{ "status": "ok", "database": "connected" }`

| Method + path | Purpose |
|---|---|
| `GET /health` | Liveness + DB probe |
| `POST /payments` | Create a payment and synchronously drive risk -> reserve -> provider in one request |
| `GET /payments/{id}` | Retrieve a payment and its current state |
| `GET /payments/{id}/events` | Append-only state-transition history |
| `POST /payments/{id}/reconcile` | Resolve an `UNKNOWN` payment against the pinned provider |
| `POST /payments/{id}/callback` | Ingest an asynchronous provider outcome, deduped on `(provider, provider_reference)` |
| `GET /outbox/pending` | Inspect unpublished outbox events |
| `POST /outbox/publish` | Relay pending events to the broker |

**Key request/response shapes.**
- `POST /payments` (`PaymentCreate`): `account_id` (UUID), `amount` (Decimal > 0,
  2dp), `destination` (str, 1-200). Returns `201` `PaymentResponse`: `id`,
  `account_id`, `amount`, `destination`, `state`, `provider`, `reserve_tx_id`,
  `capture_tx_id`, `release_tx_id`, `correlation_id`, `created_at`.
- `POST /payments/{id}/reconcile`: `409` if the payment is not in `UNKNOWN`.
- `POST /payments/{id}/callback` (`ProviderCallback`): `provider`,
  `provider_reference`, `outcome`. Returns `{ "status": "duplicate|ignored|processed" }`.

**Payment states** (`state` value): `received`, `risk_pending`, `risk_review`,
`rejected`, `approved`, `reserving`, `funds_reserved`, `provider_pending`,
`capturing`, `releasing`, `unknown`, `settled`, `failed`. Terminal: `rejected`,
`settled`, `failed`.

**Lifecycle.** Risk gate first: `block` -> `rejected`, `review` -> `risk_review`
(held), `allow` -> reserve. Reserve moves customer -> suspense before any provider
call. Provider outcome: `success` -> capture -> `settled`; `failed` -> release ->
`failed`; `timeout` -> pinned `unknown` (never falls back until reconciled);
`unavailable` -> try next provider, and if all are unavailable, release -> `failed`.
Risk-engine unreachable fails safe to `review`. Providers (`NorthPay`, `RapidPay`,
`LegacyPay`) are weighted random simulators, so a fresh payment's terminal state
is not deterministic.

**Produces** onto **`payment-events`**: `payment.received`, `payment.approved`,
`payment.rejected`, `payment.reserved`, `payment.reservation_failed`,
`payment.provider_succeeded`, `payment.provider_failed`, `payment.captured`,
`payment.settled`, `payment.released`, `payment.failed`, `payment.unknown`.
**Consumes:** nothing over Pub/Sub; calls the ledger and risk engine synchronously
over HTTP.

---

## Risk Engine

Deterministic, explainable, weighted-rules decisioning (ABS-REQ-013 to ABS-REQ-016).
A synchronous decision path independent of an asynchronous behavioural-state feed.

- **Live:** `https://risk-engine-eppidgbmxa-nw.a.run.app`
- **Auth:** none on the business API; `POST /events/pubsub` requires an OIDC push token.
- **Health:** `{ "status": "ok", "database": "connected" }`

| Method + path | Auth | Purpose |
|---|---|---|
| `GET /health` | none | Liveness + DB probe |
| `POST /risk/evaluate` | none | Synchronously score a payment and record the decision |
| `GET /decisions/{evaluation_id}` | none | Retrieve a decision by its evaluation id |
| `POST /events/pubsub` | OIDC push | Consume behavioural-state events (builds the state the sync path reads) |
| `GET /outbox/pending` | none | Inspect unpublished outbox events |
| `POST /outbox/publish` | none | Relay pending events to the broker |

**Key request/response shapes.**
- `POST /risk/evaluate` (`EvaluateRequest`): `evaluation_id` (UUID, idempotency
  key), `payment_id` (UUID), `account_id` (UUID), `amount` (Decimal > 0),
  `destination` (str), `correlation_id` (UUID, optional). Returns `EvaluateResponse`:
  `decision_id`, `evaluation_id`, `decision` (`allow`|`review`|`block`), `band`
  (uppercase decision), `score` (int 0-100), `rule_version`, `rule_config_hash`,
  `reasons` (`[{ rule, weight }]`), `state_age_seconds`, `correlation_id`,
  `evaluated_at`. Same `evaluation_id` with a different body: `409`.

**Decisioning.** Score is the sum of fired-rule weights, capped at 100. Bands:
`>= 70` block, `>= 40` review, else allow. If state is stale and the score would
otherwise allow, it is floored up to review: uncertainty never moves money.
`rule_version` and `rule_config_hash` make a decision replayable; the same snapshot
and rule version always yield the same result.

**Produces** exactly one event, `risk.evaluated`, onto **`risk-events`**. Payload:
`decision_id`, `evaluation_id`, `payment_id`, `account_id`, `decision`, `band`,
`score`, `reasons`, `rule_version`. There is no `risk.alert.created` or any other
emitted type.
**Consumes** (via `/events/pubsub`): `payment.received`, `payment.failed`,
`payment.rejected` update behavioural state; other types are recorded as
observations only.

---

## Notification Service

A strict downstream sink (ABS-REQ-006). Turns payment and risk events into
customer-facing messages, and exposes delivery records over a read API. It
publishes nothing and has no outbound broker path; its isolation is the point.

- **Live:** `https://notification-service-eppidgbmxa-nw.a.run.app`
- **Auth:** none on the read API; `POST /events/pubsub` requires an OIDC push token.
- **Health:** `{ "status": "ok", "database": "connected" }`

| Method + path | Auth | Purpose |
|---|---|---|
| `GET /health` | none | Liveness + DB probe |
| `GET /notifications/{payment_id}` | none | All deliveries produced for a payment |
| `POST /events/pubsub` | OIDC push | Consume events and fan out to channels (the only write path) |

**Delivery record** (`GET /notifications/{payment_id}` -> `NotificationsOut`):
`payment_id` and `deliveries[]`, each: `id`, `event_id`, `channel`
(`email`|`sms`), `destination` (simulated), `status`
(`pending`|`delivered`|`failed_retryable`|`dead_lettered`), `attempt_count`,
`provider_reference` (null until delivered), `correlation_id`, `created_at`,
`delivered_at`, and `attempts[]` (`attempt_number`, `outcome`, `error`,
`attempted_at`). Unknown payment returns an empty `deliveries` list, not `404`.

**Consumer behaviour.** `/events/pubsub` returns `200` with `status`
`ignored`/`processed`; if any channel is still retryable it returns `503` so the
broker redelivers. Idempotency is per `(event_id, channel)`: a unique DB
constraint plus a per-channel provider key means at-least-once redelivery never
double-notifies a channel.

**Fan-out map** (`plan_notifications`, requires `payload.account_id`):
`payment.settled` -> email + SMS; `payment.failed` -> email + SMS;
`payment.rejected` -> email; `risk.evaluated` with `decision` in `review`/`block`
-> email; everything else -> nothing.

**Produces:** nothing (strict sink).
**Consumes:** **`payment-events`** and **`risk-events`** (push subscriptions
`payment-events-to-notification`, `risk-events-to-notification`; dead-letter
`notification-events-deadletter`).

---

## Analytics Service

Event-sourced CQRS read model over BigQuery (ABS-REQ-006 sink; ABS-REQ-008 dedup).
A durable raw-event history plus deterministic projections rebuildable from it.

- **Live:** `https://analytics-service-eppidgbmxa-nw.a.run.app`
- **Auth:** none on the read API; `POST /events/pubsub` requires an OIDC push token.
- **Health:** `{ "status": "ok", "backend": "bigquery" }` (`backend` reflects the
  configured store: `bigquery` in production, `memory` locally).

| Method + path | Auth | Purpose |
|---|---|---|
| `GET /health` | none | Liveness + active store backend |
| `GET /analytics/overview` | none | Headline platform metrics |
| `GET /analytics/payments` | none | Payment volumes and settlement outcomes |
| `GET /analytics/risk` | none | Distribution of risk decisions |
| `GET /analytics/providers` | none | Per-provider settlement performance |
| `GET /analytics/timeseries` | none | Daily platform metrics |
| `GET /analytics/accounts/{account_id}` | none | Activity summary for one account |
| `POST /events/pubsub` | OIDC push | Ingest an event into raw history (the only write path) |

**Watermark.** Every `/analytics/*` response (except the single-account one, which
nests under `account`) wraps its projection as `{ "watermark": { "raw_event_count":
int, "as_of": str|null }, "<name>": <projection> }`. `as_of` is the max
`ingested_at` in the canonical set (deterministic), not wall-clock, so eventual
consistency is visible and reproducible.

**Ingest.** `/events/pubsub` returns `{ "status": "recorded"|"duplicate",
"event_id": ... }`, idempotent on `event_id`. It normalizes both wire formats: the
full ABS envelope in `message.data` (orchestrator, risk), and the ledger's
attribute-style form (payload in `data`, `event_id`/`event_type` in
`message.attributes`). Persisting the raw event is the durable action; projections
are refreshed off that path, never inline.

**Refresh is not HTTP.** Materialization is a CLI (`python -m app.admin
refresh|rebuild|status|ensure`) deployed as the `analytics-refresh` Cloud Run Job
and triggered every ten minutes by Cloud Scheduler. Projections are pure
deterministic functions of raw history, so `rebuild` (drop then refresh) yields a
byte-identical result. There is no HTTP refresh, rebuild, or status endpoint.

**Produces:** nothing (strict sink).
**Consumes:** **`transaction-events`**, **`payment-events`**, **`risk-events`**
(one push subscription per topic to `/events/pubsub`, each with a dead-letter).

---

## Topics and flow

| Topic | Owner (producer) | Consumers |
|---|---|---|
| `transaction-events` | ledger-api | analytics |
| `payment-events` | payment-orchestrator | risk, notification, analytics |
| `risk-events` | risk-engine | notification, analytics |

The topics are owned by platform-infrastructure and referenced by producers and
consumers; no service creates another's topic. Notification and analytics are pure
sinks: they consume and never publish.

A single payment therefore fans out like this: `POST /payments` drives a
synchronous ledger reservation and a synchronous risk decision, then, once the
producers' outboxes are drained, `payment-events` reaches risk, notification and
analytics, `risk-events` reaches notification and analytics, and
`transaction-events` reaches analytics. Because every relay is manual and every
consumer idempotent, a verifier controls exactly when events propagate and can
assert the same outcome under redelivery.

## Notes for the verification harness and portal

These are the constraints the discovery surfaced. They are binding on both the
harness and the portal, so neither is built against an interface that does not
exist.

- **Treat every service as a black box.** Drive it only through the endpoints
  above; assert only on their responses and on published events observed through a
  consumer's read API. Never read a service database or queue directly.
- **The ledger needs a token; nothing else does.** Get one from `POST /auth/token`
  as `admin` for write flows, or `auditor` for `GET /audit/*`.
- **To make events propagate, drain outboxes.** After a write, call the relevant
  producer's `POST /outbox/publish` before asserting a consumer saw the event.
- **There is no payment-list endpoint.** The orchestrator exposes create, get by
  id, event history, reconcile and callback; it does not list payments. The portal
  and the harness key on a known payment id, correlation id, or verification-run
  record, never on a "recent payments" query. A list would require a new read-only
  orchestrator endpoint, deliberately out of MVP scope.
- **Payment creation is not idempotent.** `POST /payments` takes no idempotency
  key; two identical HTTP requests create two independent payments. The
  at-most-once property is not at creation, it is at the ledger-effect level: each
  payment's reserve, capture and release are deterministic, idempotently keyed
  ledger operations (ABS-REQ-002, ABS-REQ-005), and duplicate provider callbacks
  are deduplicated on `(provider, provider_reference)` (ABS-REQ-003). Duplicate
  safety is proven there, never by claiming the creation API is idempotent.
- **Tracing crosses services by `correlation_id`, except into the ledger.** The
  `correlation_id` threads the payment (`GET /payments/{id}`), the risk decision
  (its record and `risk.evaluated`), and every downstream notification and
  analytics event. The ledger transaction does not carry a `correlation_id`; its
  payload is `transaction_id`, `type`, `amount`, `idempotency_key`, `reference`.
  A trace reaches the ledger financial effect through the orchestrator's recorded
  `reserve_tx_id` / `capture_tx_id` / `release_tx_id`, not through a fabricated
  ledger correlation field.
- **Analytics has no status endpoint; the watermark is the status.** Do not expect
  or add `GET /status` on analytics. Every `/analytics/*` response carries
  `watermark { raw_event_count, as_of }`; that is how the harness and portal read
  freshness. Refresh and rebuild stay operational CLI / Cloud Run Job tooling, not
  an HTTP mutation.
- **Providers are stochastic.** A single `POST /payments` may settle, fail, or go
  unknown. Assert on invariants (balance conservation, at-most-once effect, a
  notification exists for a terminal payment) rather than a fixed terminal state,
  or drive deterministic edges through `/callback` and `/reconcile`.
- **Analytics and notification are eventually consistent.** Analytics projections
  lag ingest until a refresh runs; a notification delivery lags until its push is
  processed. Poll with a bounded wait, and use the analytics watermark to know what
  the projection currently reflects.
