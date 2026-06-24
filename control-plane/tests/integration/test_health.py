"""Integration tests for health/readiness endpoints (ASGI, no network)."""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_health_live_is_always_ok(app_factory) -> None:
    app = app_factory()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_returns_version(app_factory) -> None:
    app = app_factory()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert "version" in resp.json()


@pytest.mark.asyncio
async def test_readiness_ok_when_dependencies_healthy(app_factory) -> None:
    app = app_factory()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert all(dep["healthy"] for dep in body["dependencies"])


@pytest.mark.asyncio
async def test_readiness_503_when_redis_down(app_factory) -> None:
    app = app_factory(redis_fail=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"


@pytest.mark.asyncio
async def test_request_id_header_present(app_factory) -> None:
    app = app_factory()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health/live")
    assert resp.headers.get("X-Request-ID")
