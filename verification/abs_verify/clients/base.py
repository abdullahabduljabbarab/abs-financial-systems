"""Shared HTTP plumbing for the service clients."""

from __future__ import annotations

import time
from typing import Any, Callable

import httpx

from ..config import Config


class ServiceError(RuntimeError):
    """An HTTP call to a service returned an unexpected status."""

    def __init__(self, service: str, method: str, url: str, status: int, body: str):
        self.service = service
        self.status = status
        self.body = body
        super().__init__(f"{service} {method} {url} -> {status}: {body[:400]}")


class PollTimeout(RuntimeError):
    """A bounded wait for an eventually-consistent condition expired."""


class BaseClient:
    """A thin wrapper over httpx for one service's base URL."""

    service = "service"

    def __init__(self, base_url: str, config: Config):
        self.base_url = base_url.rstrip("/")
        self.config = config
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=config.http_timeout,
            verify=config.verify,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        expect: tuple[int, ...] = (200, 201),
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        resp = self._http.request(method, path, headers=headers, **kwargs)
        if resp.status_code not in expect:
            raise ServiceError(self.service, method, path, resp.status_code, resp.text)
        return resp

    def get_json(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs).json()

    def post_json(self, path: str, **kwargs: Any) -> Any:
        return self._request("POST", path, **kwargs).json()

    def health(self) -> dict[str, Any]:
        return self.get_json("/health")

    def poll_until(
        self,
        fetch: Callable[[], Any],
        predicate: Callable[[Any], bool],
        *,
        timeout: float | None = None,
        interval: float | None = None,
        describe: str = "condition",
    ) -> Any:
        """Call `fetch` until `predicate` holds, or raise PollTimeout.

        Used for the eventually-consistent legs (a notification delivery landing, a
        projection catching up after a refresh). Returns the last fetched value.
        """
        timeout = self.config.poll_timeout if timeout is None else timeout
        interval = self.config.poll_interval if interval is None else interval
        deadline = time.monotonic() + timeout
        last: Any = None
        while True:
            last = fetch()
            if predicate(last):
                return last
            if time.monotonic() >= deadline:
                raise PollTimeout(f"{self.service}: timed out waiting for {describe}")
            time.sleep(interval)
