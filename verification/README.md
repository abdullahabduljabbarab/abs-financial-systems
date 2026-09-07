# Verification Harness

Black-box system verification for ABS Financial Systems. The harness drives the
five live services only through their public HTTP surface
([../docs/SERVICE_CATALOGUE.md](../docs/SERVICE_CATALOGUE.md)) and asserts on their responses
and on the events observed through consumers' read APIs. It never reads a service
database or queue. Each scenario maps to the system requirements in
[../docs/SYSTEM_REQUIREMENTS.md](../docs/SYSTEM_REQUIREMENTS.md) and the plan in
[../docs/VERIFICATION_PLAN.md](../docs/VERIFICATION_PLAN.md), and produces one immutable
evidence file.

## Layout

```
abs_verify/
  config.py          resolved configuration (env-driven, live defaults)
  models.py          typed read views over the service responses
  clients/           one typed black-box client per service
  ops.py             controlled operator tooling (e.g. the analytics refresh job)
  evidence.py        immutable per-run evidence records
  scenarios/         the SYS-V-* scenarios
  runner.py          CLI entry point
evidence/            per-run evidence output (one JSON per run)
```

The clients are the contract boundary: `LedgerClient`, `OrchestratorClient`,
`RiskClient`, `NotificationClient`, `AnalyticsClient`. A scenario composes them; it
never talks to anything else.

## Running

```
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt        # Windows
# .venv/bin/pip install -r requirements.txt          # Linux/macOS

python -m abs_verify.runner --list
python -m abs_verify.runner sys-v-001
```

Exit code is `0` if every assertion passed, non-zero otherwise. Each run writes
`evidence/<scenario>/<run-id>.json`, recording every id captured and every
assertion with its pass/fail. Evidence files are never overwritten.

### Configuration

Defaults target the live ecosystem; override anything via the environment
(`ABS_LEDGER_URL`, `ABS_ORCHESTRATOR_URL`, ..., `ABS_LEDGER_ADMIN_PASSWORD`,
`ABS_EVIDENCE_DIR`, the poll timeouts). See `abs_verify/config.py`.

### Two local-run notes

- **TLS-inspecting networks.** If Python cannot verify the services' certificates
  (a corporate or antivirus proxy re-signs TLS), the harness trusts the OS
  certificate store automatically via `truststore`. On clean CI this is a no-op.
- **The analytics refresh.** Analytics projections refresh off the ingest path, via
  a Cloud Run Job, so SYS-V-001 triggers that job as controlled operator tooling.
  Point `ABS_GCLOUD` at your `gcloud` binary (it is called as
  `gcloud run jobs execute <job> --wait`). Without gcloud the harness falls back to
  waiting for the scheduled refresh within the poll window.

## Status

All thirteen scenarios (SYS-V-001..013) run green against the live ecosystem,
covering every system requirement in
[../docs/SYSTEM_REQUIREMENTS.md](../docs/SYSTEM_REQUIREMENTS.md), including the
failure-injection scenarios. Run the whole suite with:

```
python -m abs_verify.runner all
```

The failure-mode scenarios use controlled operator tooling that always restores the
deployment on exit (`abs_verify/ops.py`): the provider-outcome seam (SYS-V-004/005),
an unreachable-risk override (SYS-V-007), Pub/Sub push cuts (SYS-V-008/013), and a
duplicate publish (SYS-V-009). These need `ABS_GCLOUD` set.
