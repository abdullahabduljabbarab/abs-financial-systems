"""The portal BFF application.

Read-only `/api` endpoints that aggregate the services, plus serving the built
frontend. No database, no writes, no privileged credentials.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

# On a TLS-inspecting network, trust the OS store so outbound HTTPS verifies. A no-op
# on a clean host (Cloud Run), where system certs already work.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001 - trust injection is a convenience, never fatal
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import load_config
from .matrix import matrix
from .services import Services
from .trace import assemble_trace

_ANALYTICS_VIEWS = {"overview", "payments", "risk", "providers", "timeseries"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.services = Services(load_config())
    try:
        yield
    finally:
        await app.state.services.aclose()


app = FastAPI(title="ABS Engineering Portal BFF", version="0.1.0", lifespan=lifespan)

# Read-only, public data; permissive CORS keeps frontend development simple. In
# production the frontend is served from this same origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _services(app: FastAPI) -> Services:
    return app.state.services


@app.get("/healthz", tags=["System"], summary="BFF liveness")
async def healthz():
    return {"status": "ok"}


@app.get("/api/health", tags=["Portal"], summary="Aggregate health of every service")
async def api_health():
    return await _services(app).health()


@app.get("/api/verification", tags=["Portal"], summary="The requirement-to-scenario matrix")
async def api_verification():
    return matrix()


@app.get("/api/analytics/{view}", tags=["Portal"], summary="A read-only analytics projection")
async def api_analytics(view: str):
    if view not in _ANALYTICS_VIEWS:
        raise HTTPException(status_code=404, detail=f"unknown analytics view '{view}'")
    return await _services(app).analytics(view)


@app.get("/api/trace/{payment_id}", tags=["Portal"], summary="A payment's cross-service trace")
async def api_trace(payment_id: str):
    trace = await assemble_trace(_services(app), payment_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="payment not found")
    return trace


# Serve the built frontend if present (produced in M4). Kept last so it does not
# shadow the API routes. The BFF runs standalone as an API before the frontend exists.
_FRONTEND_DIST = os.environ.get(
    "PORTAL_FRONTEND_DIST",
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"),
)
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
