"""Aggregates all v1 API routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import (
    admin,
    agent,
    api_keys,
    auth,
    builds,
    domains,
    github,
    integrations,
    payments,
    tenants,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(builds.router)
api_router.include_router(payments.router)
api_router.include_router(api_keys.router)
api_router.include_router(admin.router)
api_router.include_router(agent.router)
api_router.include_router(domains.router)
api_router.include_router(integrations.router)
api_router.include_router(github.router)

# Health probes are mounted at the app root (see app/main.py).
