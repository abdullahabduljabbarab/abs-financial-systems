"""Ledger API client. The only service that authenticates (Bearer JWT)."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..models import Account, Balance, Token, Transaction
from .base import BaseClient


class LedgerClient(BaseClient):
    service = "ledger-api"

    def __init__(self, config: Config):
        super().__init__(config.ledger_url, config)
        self._token: str | None = None

    # --- auth ---------------------------------------------------------------

    def login(self, user: str | None = None, password: str | None = None) -> str:
        """Exchange seed credentials for a bearer JWT and remember it."""
        data = {
            "username": user or self.config.ledger_admin_user,
            "password": password or self.config.ledger_admin_password,
        }
        token = Token.model_validate(self.post_json("/auth/token", data=data))
        self._token = token.access_token
        return self._token

    @property
    def _auth(self) -> dict[str, str]:
        if not self._token:
            self.login()
        return {"Authorization": f"Bearer {self._token}"}

    # --- accounts and transactions -----------------------------------------

    def create_account(self, name: str) -> Account:
        return Account.model_validate(
            self.post_json("/accounts", json={"name": name}, headers=self._auth)
        )

    def balance(self, account_id: str) -> Balance:
        return Balance.model_validate(
            self.get_json(f"/accounts/{account_id}/balance", headers=self._auth)
        )

    def deposit(self, account_id: str, amount: str, idempotency_key: str) -> Transaction:
        body = {
            "idempotency_key": idempotency_key,
            "type": "deposit",
            "amount": amount,
            "account_id": account_id,
        }
        return Transaction.model_validate(
            self.post_json("/transactions", json=body, headers=self._auth)
        )

    def create_transaction(self, body: dict[str, Any]) -> Transaction:
        return Transaction.model_validate(
            self.post_json("/transactions", json=body, headers=self._auth)
        )

    def list_transactions(
        self, account_id: str | None = None, txn_type: str | None = None
    ) -> list[Transaction]:
        """Walk the cursor-paginated transaction list, optionally filtered."""
        params: dict[str, Any] = {"limit": 100}
        if account_id:
            params["account_id"] = account_id
        if txn_type:
            params["type"] = txn_type
        out: list[Transaction] = []
        cursor: str | None = None
        while True:
            if cursor:
                params["cursor"] = cursor
            page = self.get_json("/transactions", params=params, headers=self._auth)
            out.extend(Transaction.model_validate(t) for t in page["items"])
            cursor = page.get("next_cursor")
            if not cursor:
                return out

    def transactions_with_key(self, account_id: str, idempotency_key: str) -> list[Transaction]:
        """Every transaction on an account carrying an exact idempotency key.

        This is how at-most-once ledger effect is proven: exactly one transaction
        should carry `payment:{id}:capture`, `:reserve`, or `:release`.
        """
        return [
            t
            for t in self.list_transactions(account_id=account_id)
            if t.idempotency_key == idempotency_key
        ]

    # --- audit --------------------------------------------------------------

    def audit_verify(self) -> dict[str, Any]:
        return self.get_json("/audit/verify", headers=self._auth)

    def audit_chain(self) -> dict[str, Any]:
        return self.get_json("/audit/chain", headers=self._auth)

    # --- outbox -------------------------------------------------------------

    def publish_outbox(self, limit: int = 200) -> dict[str, Any]:
        return self.post_json("/outbox/publish", params={"limit": limit}, headers=self._auth)
