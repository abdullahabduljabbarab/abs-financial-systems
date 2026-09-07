"""Command-line entry point for the verification harness.

    python -m abs_verify.runner sys-v-001
    python -m abs_verify.runner --list

Runs a scenario against the live ecosystem, writes one immutable evidence file, and
exits non-zero if any assertion failed.
"""

from __future__ import annotations

import sys
import traceback

from .config import load_config
from .evidence import AssertionFailed, Evidence
from .scenarios import REGISTRY, World


def _enable_local_trust() -> None:
    """On a TLS-inspecting network, trust the OS store so httpx can verify.

    Best-effort: absent on clean CI (Linux), where system certs already work.
    """
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:  # noqa: BLE001 - trust injection is a convenience, never fatal
        pass


def _print_summary(ev: Evidence, evidence_path: str) -> None:
    mark = "PASS" if ev.passed else "FAIL"
    print(f"\n[{mark}] {ev.scenario_id}  {ev.title}  ({', '.join(ev.covers)})")
    for a in ev.assertions:
        flag = "ok  " if a.passed else "FAIL"
        print(f"  {flag} {a.name}")
        if not a.passed:
            print(f"       {a.detail}")
    if ev.error:
        print(f"  error: {ev.error}")
    print(f"  evidence: {evidence_path}")


def run_scenario(scenario_id: str) -> int:
    scenario_cls = REGISTRY.get(scenario_id)
    if scenario_cls is None:
        print(f"unknown scenario '{scenario_id}'. Known: {', '.join(sorted(REGISTRY))}")
        return 2

    config = load_config()
    scenario = scenario_cls()
    ev = Evidence(scenario.id, scenario.title, scenario.covers, config.evidence_dir)
    world = World.from_config(config)
    try:
        if getattr(scenario, "requires_provider_hooks", False):
            from .ops import provider_hooks

            with provider_hooks(config, ev):
                scenario.run(world, ev)
        else:
            scenario.run(world, ev)
    except AssertionFailed as exc:
        # A required assertion failed; it is already recorded on the evidence.
        ev.error = str(exc)
    except Exception as exc:  # noqa: BLE001 - the harness records any failure as evidence
        ev.error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    finally:
        world.close()

    path = ev.write()
    _print_summary(ev, path)
    return 0 if ev.passed else 1


def run_all() -> int:
    """Run every scenario in id order; return non-zero if any failed."""
    results: list[tuple[str, bool]] = []
    for sid in sorted(REGISTRY):
        code = run_scenario(sid)
        results.append((sid, code == 0))
    passed = sum(1 for _, ok in results if ok)
    print(f"\n===== {passed}/{len(results)} scenarios passed =====")
    for sid, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {sid}")
    return 0 if passed == len(results) else 1


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    _enable_local_trust()
    if argv[0] == "--list":
        for sid, cls in sorted(REGISTRY.items()):
            print(f"{sid}  {cls.title}  ({', '.join(cls.covers)})")
        return 0
    if argv[0] == "all":
        return run_all()
    return run_scenario(argv[0])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
