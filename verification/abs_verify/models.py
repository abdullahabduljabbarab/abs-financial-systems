"""Typed views over the service responses the harness reasons about.

These mirror the response shapes in ../docs/SERVICE_CATALOGUE.md. They are read models:
the harness parses what a service returns, it never constructs a service's internal
state. `extra="allow"` keeps forward-compatible fields the harness does not name.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class _Read(BaseModel):
    model_config = ConfigDict(extra="allow")


class Token(_Read):
    access_token: str
    token_type: str


class Account(_Read):
    id: str
    name: str
    is_system: bool | None = None


class Balance(_Read):
    account_id: str
    balance: Decimal


class Transaction(_Read):
    id: str
    idempotency_key: str
    type: str
    amount: Decimal
    reference: str | None = None


class Payment(_Read):
    id: str
    account_id: str
    amount: Decimal
    destination: str
    state: str
    provider: str | None = None
    reserve_tx_id: str | None = None
    capture_tx_id: str | None = None
    release_tx_id: str | None = None
    correlation_id: str


class Decision(_Read):
    decision_id: str
    evaluation_id: str
    decision: str
    band: str
    score: int
    rule_version: str
    rule_config_hash: str | None = None
    correlation_id: str


class Delivery(_Read):
    id: str
    event_id: str
    channel: str
    destination: str
    status: str
    attempt_count: int
    provider_reference: str | None = None
    correlation_id: str | None = None


class Notifications(_Read):
    payment_id: str
    deliveries: list[Delivery]


class Watermark(_Read):
    raw_event_count: int
    as_of: str | None = None
