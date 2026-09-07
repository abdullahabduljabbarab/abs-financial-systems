# Engineering Portal

A read-only engineering and operations surface over the live ABS ecosystem: system
health, a cross-service payment trace, the verification matrix, and analytics reads.
It is not a customer banking UI, and it is not a financial service. It holds no
database, performs no writes, and uses no privileged credentials; it only calls the
services' public read APIs and composes the answers.

**Live:** https://abs-portal-eppidgbmxa-nw.a.run.app

![Portal payment trace](../docs/images/portal-trace.png)

One Cloud Run service, `abs-portal`, serves both halves:

- **`bff/`** (this milestone). A FastAPI backend-for-frontend that aggregates the
  services. Endpoints:
  - `GET /api/health` aggregate health of all five services, with latencies.
  - `GET /api/trace/{payment_id}` a payment's cross-service trace: its state and
    lifecycle timeline, the ledger effect (the recorded reserve, capture and release
    transaction ids), the notification deliveries, and the analytics event trace
    (including the risk decision), joined by the payment's `correlation_id`.
  - `GET /api/verification` the requirement-to-scenario matrix.
  - `GET /api/analytics/{view}` a read-only analytics projection
    (`overview`, `payments`, `risk`, `providers`, `timeseries`).
  - `GET /healthz` the BFF's own liveness.
- **`frontend/`**. A React + TypeScript + Vite single-page app, served by the BFF,
  with a dark control-surface identity. Four views: **System** (live health of every
  service), **Payment Trace** (enter a payment id to follow it across services: its
  lifecycle, ledger effect, notifications, and the analytics event trace), **Verification**
  (the requirement-to-scenario matrix), and **Analytics** (the read-model projections).

## Running the BFF

```
cd bff
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt        # Windows
.venv/Scripts/python -m uvicorn app.main:app --port 8080
```

By default it targets the live services; override any upstream with
`PORTAL_LEDGER_URL`, `PORTAL_ORCHESTRATOR_URL`, `PORTAL_RISK_URL`,
`PORTAL_NOTIFICATION_URL`, `PORTAL_ANALYTICS_URL`. On a TLS-inspecting network the
BFF trusts the OS certificate store automatically; on Cloud Run that is a no-op.

The BFF serves the built frontend from `frontend/dist` when it exists, so it runs
standalone as an API until the frontend is built.

## Running the frontend

For the integrated app (one origin), build the frontend and run the BFF:

```
cd frontend && npm install && npm run build
cd ../bff && .venv/Scripts/python -m uvicorn app.main:app --port 8080
# open http://localhost:8080
```

For frontend development with hot reload, run the BFF on :8080 and the Vite dev
server separately; it proxies `/api` and `/healthz` to the BFF:

```
cd frontend && npm run dev        # http://localhost:5173
```

## Boundaries

The portal observes; it never participates in financial state. It reaches no
service database or queue, and the ledger's authoritative reads that require
authentication are deliberately out of scope: the payment trace presents the ledger
effect through the transaction ids the orchestrator already records, not by reading
the ledger as a privileged user.
