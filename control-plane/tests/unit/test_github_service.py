"""Unit tests for GithubService (GitHub via Nango) with mocked HTTP."""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.config import Settings
from app.services.github_service import GithubService


def _service(monkeypatch, handler) -> GithubService:
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def patched(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched)
    return GithubService(
        settings=Settings(
            _env_file=None,
            jwt_private_key="x",
            jwt_public_key="x",
            nango_secret_key="secret",
            nango_base_url="https://nango.test",
        )
    )


@pytest.mark.asyncio
async def test_status_connected(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connections":
            return httpx.Response(
                200,
                json={"connections": [{"provider_config_key": "github", "connection_id": "c1"}]},
            )
        return httpx.Response(404)

    svc = _service(monkeypatch, handler)
    assert (await svc.get_status(uuid.uuid4()))["connected"] is True


@pytest.mark.asyncio
async def test_status_not_connected(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"connections": []})

    svc = _service(monkeypatch, handler)
    assert (await svc.get_status(uuid.uuid4()))["connected"] is False


@pytest.mark.asyncio
async def test_get_token_reads_nango_credentials(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/connections":
            return httpx.Response(
                200,
                json={"connections": [{"provider_config_key": "github", "connection_id": "c1"}]},
            )
        if request.url.path == "/connection/c1":
            return httpx.Response(200, json={"credentials": {"access_token": "ghtok"}})
        return httpx.Response(404)

    svc = _service(monkeypatch, handler)
    assert await svc.get_token(uuid.uuid4()) == "ghtok"
