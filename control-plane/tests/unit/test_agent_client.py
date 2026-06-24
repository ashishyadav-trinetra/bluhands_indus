"""Unit tests for HttpAgentClient + agent client factory."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.tasks.agent_client import HttpAgentClient, StubAgentClient, get_agent_client


def _patch_httpx(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/builds":
            return httpx.Response(202, json={"job_id": "job-1"})
        if request.method == "GET" and request.url.path == "/builds/job-1":
            return httpx.Response(
                200, json={"status": "success", "preview_url": "https://p/b1", "error": None}
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def patched(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched)


@pytest.mark.asyncio
async def test_http_agent_client_start_and_status(monkeypatch) -> None:
    _patch_httpx(monkeypatch)
    client = HttpAgentClient("http://agent:8100", timeout_seconds=5)
    job_id = await client.start_build("b1", prompt="p", tenant_id="t1", industry="ecommerce")
    assert job_id == "job-1"
    status = await client.get_status("job-1")
    assert status["status"] == "success"
    assert status["preview_url"] == "https://p/b1"


def test_factory_defaults_to_stub() -> None:
    s = Settings(_env_file=None, jwt_private_key="x", jwt_public_key="x")
    assert isinstance(get_agent_client(s), StubAgentClient)


def test_factory_http_when_configured() -> None:
    s = Settings(_env_file=None, jwt_private_key="x", jwt_public_key="x", agent_mode="http")
    assert isinstance(get_agent_client(s), HttpAgentClient)
