"""The verification matrix is internally consistent: every requirement is mapped and
every scenario points at real requirements."""

from app.matrix import REQUIREMENTS, SCENARIOS, matrix


def test_every_requirement_is_covered_or_noted():
    m = matrix()
    for req in m["requirements"]:
        covered = bool(req["scenarios"])
        noted = bool(req.get("note"))
        assert covered or noted, f"{req['id']} has neither a scenario nor a note"


def test_scenarios_reference_real_requirements():
    ids = {r["id"] for r in REQUIREMENTS}
    for scenario in SCENARIOS:
        for req in scenario["covers"]:
            assert req in ids, f"{scenario['id']} references unknown {req}"


def test_totals_match():
    m = matrix()
    assert m["totals"] == {"requirements": len(REQUIREMENTS), "scenarios": len(SCENARIOS)}
    assert m["totals"] == {"requirements": 16, "scenarios": 13}
