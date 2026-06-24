"""Integration tests for the agent HTTP API (offline, DryRun)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from agent.app import create_app
from agent.config import Settings


def _app(tmp_path):
    settings = Settings(_env_file=None, dry_run=True, workspace_root=tmp_path)
    return create_app(settings)


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_health(tmp_path) -> None:
    async with _client(_app(tmp_path)) as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_start_build_then_poll_to_success(tmp_path) -> None:
    async with _client(_app(tmp_path)) as c:
        started = await c.post(
            "/builds",
            json={"build_id": "b1", "prompt": "shop", "tenant_id": "t1", "industry": "ecommerce"},
        )
        assert started.status_code == 202
        job_id = started.json()["job_id"]
        assert job_id.startswith("job-")

        # Poll until the background DryRun job finishes.
        for _ in range(20):
            status = await c.get(f"/builds/{job_id}")
            assert status.status_code == 200
            if status.json()["status"] != "running":
                break
            await asyncio.sleep(0.02)

    body = status.json()
    assert body["status"] == "success"
    assert body["preview_url"].endswith("/b1")
    assert body["error"] is None


@pytest.mark.asyncio
async def test_status_unknown_job_404(tmp_path) -> None:
    async with _client(_app(tmp_path)) as c:
        r = await c.get("/builds/nope")
    assert r.status_code == 404
