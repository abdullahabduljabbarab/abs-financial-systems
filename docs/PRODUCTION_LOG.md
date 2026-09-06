# Production Log

A running record of what the umbrella repository was built and verified, in what
order, and why. Newest last.

The umbrella is the system layer over the ecosystem. It owns no financial, payment,
risk, notification, analytics or infrastructure state; its work is the cross-service
contracts, the verification that proves the system-level requirements hold, and (to
come) a read-only engineering portal. Every milestone is done against the real,
deployed services, never stubs.

## Milestone 0: Discovery

**Goal:** Build the umbrella against the interfaces the deployed system actually
has, not the ones the spec imagined. Inspect the five service repositories, record
their real external contract, and reconcile the system-level docs against it before
writing any code.

**Done:**
- [SERVICE_CATALOGUE.md](SERVICE_CATALOGUE.md): the black-box HTTP surface of all
  five services, drawn from their code, endpoints, auth, request and response
  shapes, the orchestrator's state machine, the events each produces and consumes.
- [VERIFICATION_PLAN.md](VERIFICATION_PLAN.md): SYS-V-001 to SYS-V-013, each mapped
  to a system requirement, with the injection method and the exact assertions.
- [EVENT_CATALOGUE.md](EVENT_CATALOGUE.md) reconciled to the code (the ledger emits
  `transaction.{deposit,withdrawal,transfer}`, risk emits only `risk.evaluated`,
  there is no notification topic), and [SYSTEM_REQUIREMENTS.md](SYSTEM_REQUIREMENTS.md)
  corrected where the code disagreed with it.

**Corrections the discovery forced, before any implementation:**
- There is no payment-list endpoint. The harness and portal key on a known payment
  id, correlation id, or verification run, never a "recent payments" query.
- Payment creation is not idempotent. At-most-once is proven at the ledger-effect
  level (deterministic reserve, capture and release keyed on the payment id) and by
  duplicate-callback dedup, never by claiming the creation API is idempotent.
- The ledger transaction carries no `correlation_id`. A trace reaches the ledger
  effect through the orchestrator's recorded reserve, capture and release
  transaction ids, not a fabricated ledger correlation field.
- Analytics has no status endpoint. Freshness is the watermark embedded in every
  projection response; refresh and rebuild stay operational Cloud Run Job tooling.

**State:** complete. The contract is frozen; implementation builds against it.

## Milestone 1: Verification foundation

**Goal:** Stand up the black-box verification harness and prove the happy path end
to end against the live ecosystem, producing evidence.

**Built** (`verification/`):
- Five typed clients, one per service, each speaking only that service's public
  HTTP surface from the catalogue.
- An immutable per-run evidence record: every id captured and every assertion, with
  its pass or fail, written once to a run-stamped file and never overwritten.
- Controlled operator tooling kept separate from the black-box clients (the
  analytics refresh runs as a Cloud Run Job, not a service API), and a runner CLI.

**Verified:** SYS-V-001 (happy-path settlement) runs green against the live
services. A funded payment settles; the customer is debited by the amount; the
payment carries a reserve and a capture and no release; the ledger's own
`audit/verify` passes; the notification is delivered on both channels carrying the
payment's `correlation_id`; and after a refresh the analytics projection shows the
settled payment with the watermark advanced. The run writes its evidence file.

**State:** complete. Next: the remaining scenarios (SYS-V-002 onward), then the
portal.
