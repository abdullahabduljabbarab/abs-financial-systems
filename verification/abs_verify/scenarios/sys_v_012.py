"""SYS-V-012: Independent ledger and projection integrity.

Covers ABS-REQ-010 (financial reconciliation can independently recover authoritative
state from ledger history), plus analytics read determinism.

The ledger's own recovery guarantees are asserted from outside: audit/verify
recomputes balances from history and checks the invariants, and audit/chain checks
the tamper-evident hash chain. Analytics is checked for deterministic reads and a
non-regressing watermark. The full rebuild-reproduction leg (rebuild yields a
byte-identical projection at the same watermark) is exercised through the
operational rebuild job and is tracked separately; it is not an HTTP mutation.
"""

from __future__ import annotations

from ..evidence import Evidence
from .base import Scenario, World


class SysV012(Scenario):
    id = "sys-v-012"
    title = "Independent ledger and projection integrity"
    covers = ["ABS-REQ-010"]

    def run(self, world: World, ev: Evidence) -> None:
        world.ledger.login()

        verify = world.ledger.audit_verify()
        ev.step("audit_verify", status=verify.get("status"), discrepancies=verify.get("discrepancies"))
        ev.require(
            "ledger audit/verify recomputes state and passes",
            verify.get("status") == "pass",
            f"status={verify.get('status')} discrepancies={verify.get('discrepancies')}",
            covers=["ABS-REQ-010"],
        )

        chain = world.ledger.audit_chain()
        ev.step("audit_chain", status=chain.get("status"), chain_length=chain.get("chain_length"))
        ev.require(
            "ledger hash chain is intact",
            chain.get("status") == "pass",
            f"status={chain.get('status')} broken={chain.get('broken_links')}",
            covers=["ABS-REQ-010"],
        )

        # Analytics: the same raw history yields the same projection. Two reads at the
        # same watermark must be identical, and the watermark must not regress.
        first = world.analytics.overview()
        second = world.analytics.overview()
        wm1 = int(first["watermark"]["raw_event_count"])
        wm2 = int(second["watermark"]["raw_event_count"])
        ev.step("analytics_reads", watermark_first=wm1, watermark_second=wm2)
        ev.check(
            "analytics watermark does not regress between reads",
            wm2 >= wm1,
            f"first={wm1} second={wm2}",
        )
        ev.check(
            "analytics projection is stable at a stable watermark",
            wm1 != wm2 or first["overview"] == second["overview"],
            "overview differed while the watermark was unchanged",
        )
