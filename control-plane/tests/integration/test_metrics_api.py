"""Integration test: /metrics endpoint records HTTP requests."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.main import create_app


def _settings() -> Settings:
    return Settings(
        _env_file=None, env="development",
        jwt_private_key="x", jwt_public_key="x",
        prometheus_enabled=True,
    )


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_request_metrics() -> None:
    settings = _settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health/live")
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "forge_http_requests_total" in body
    # the /health/live request must have been recorded by its route template
    assert "/health/live" in body
