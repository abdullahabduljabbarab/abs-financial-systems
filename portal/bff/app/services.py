"""Read-only calls to the upstream services.

Everything here is a GET against a public endpoint. The BFF never writes to a
service, never authenticates as a privileged user, and never touches a datastore.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from .config import Config


class Services:
    def __init__(self, config: Config):
        self.config = config
        self._http = httpx.AsyncClient(timeout=config.http_timeout)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, base: str, path: str, **kwargs: Any) -> httpx.Response:
        return await self._http.get(f"{base}{path}", **kwargs)

    # --- health ------------------------------------------------------------

    async def _one_health(self, name: str, base: str) -> dict[str, Any]:
        started = time.monotonic()
        try:
            resp = await self._get(base, "/health")
            latency = round((time.monotonic() - started) * 1000, 1)
            ok = resp.status_code == 200
            body = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
            return {
                "service": name,
                "healthy": ok,
                "status_code": resp.status_code,
                "latency_ms": latency,
                "detail": body,
            }
        except Exception as exc:  # noqa: BLE001 - a down service is a normal result here
            return {
                "service": name,
                "healthy": False,
                "status_code": None,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
                "detail": {"error": type(exc).__name__},
            }

    async def health(self) -> dict[str, Any]:
        services = self.config.services()
        results = await asyncio.gather(
            *(self._one_health(name, base) for name, base in services.items())
        )
        return {
            "healthy": all(r["healthy"] for r in results),
            "services": list(results),
        }

    # --- payment trace inputs ---------------------------------------------

    async def payment(self, payment_id: str) -> dict[str, Any] | None:
        resp = await self._get(self.config.orchestrator_url, f"/payments/{payment_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def payment_events(self, payment_id: str) -> list[dict[str, Any]]:
        resp = await self._get(self.config.orchestrator_url, f"/payments/{payment_id}/events")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()

    async def notifications(self, payment_id: str) -> list[dict[str, Any]]:
        resp = await self._get(self.config.notification_url, f"/notifications/{payment_id}")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json().get("deliveries", [])

    async def analytics_events(self, correlation_id: str) -> list[dict[str, Any]]:
        resp = await self._get(
            self.config.analytics_url,
            "/analytics/events",
            params={"correlation_id": correlation_id},
        )
        resp.raise_for_status()
        return resp.json().get("events", [])

    # --- analytics reads ---------------------------------------------------

    async def analytics(self, name: str) -> dict[str, Any]:
        resp = await self._get(self.config.analytics_url, f"/analytics/{name}")
        resp.raise_for_status()
        return resp.json()
