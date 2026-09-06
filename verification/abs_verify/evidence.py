"""Immutable per-run evidence.

Every scenario run produces one JSON record: what was done, every id captured, and
every assertion with its pass/fail. The record is written once, to a path stamped
with a fresh run id, and never overwritten. That is the audit trail the umbrella
exists to produce.
"""

from __future__ import annotations

import json
import os
import platform
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


class AssertionFailed(AssertionError):
    """A required assertion did not hold; the scenario cannot continue."""


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):  # pydantic models
        return _jsonable(value.model_dump())
    return value


@dataclass
class Assertion:
    name: str
    passed: bool
    detail: str
    covers: list[str] = field(default_factory=list)
    at: str = field(default_factory=_now)


@dataclass
class Step:
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    at: str = field(default_factory=_now)


class Evidence:
    """Collects one run's facts and assertions, then persists them atomically."""

    def __init__(self, scenario_id: str, title: str, covers: list[str], evidence_dir: str):
        self.scenario_id = scenario_id
        self.title = title
        self.covers = covers
        self.evidence_dir = evidence_dir
        self.run_id = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
        self.started_at = _now()
        self.finished_at: str | None = None
        self.steps: list[Step] = []
        self.assertions: list[Assertion] = []
        self.error: str | None = None
        self.host = platform.node()

    # --- recording ----------------------------------------------------------

    def step(self, name: str, **data: Any) -> None:
        self.steps.append(Step(name=name, data=_jsonable(data)))

    def check(self, name: str, passed: bool, detail: str, covers: list[str] | None = None) -> bool:
        self.assertions.append(
            Assertion(name=name, passed=bool(passed), detail=detail, covers=covers or [])
        )
        return passed

    def require(
        self, name: str, passed: bool, detail: str, covers: list[str] | None = None
    ) -> None:
        """Record an assertion and stop the run if it failed."""
        self.check(name, passed, detail, covers)
        if not passed:
            raise AssertionFailed(f"{self.scenario_id} :: {name} :: {detail}")

    # --- result -------------------------------------------------------------

    @property
    def passed(self) -> bool:
        return self.error is None and all(a.passed for a in self.assertions) and bool(
            self.assertions
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "covers": self.covers,
            "run_id": self.run_id,
            "host": self.host,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": "pass" if self.passed else "fail",
            "error": self.error,
            "assertions": [asdict(a) for a in self.assertions],
            "steps": [asdict(s) for s in self.steps],
        }

    def write(self) -> str:
        self.finished_at = _now()
        out_dir = os.path.join(self.evidence_dir, self.scenario_id)
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{self.run_id}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        return path
