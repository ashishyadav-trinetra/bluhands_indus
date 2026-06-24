"""Integration tests for API-key endpoints (offline)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import Request

from app.api.v1.dependencies.auth import get_current_user
from app.api.v1.dependencies.services import get_api_key_service
from app.core.config import Settings, get_settings
from app.db.models.user import User
from app.main import create_app
from app.services.api_key_service import ApiKeyService
from tests.fakes import InMemoryApiKeyRepo, InMemoryAudit

BASE = "http://test"
_ORG = uuid.uuid4()


def _settings() -> Settings:
    return Settings(
        _env_file=None, env="development",
        jwt_private_key="x", jwt_public_key="x", prometheus_enabled=False,
    )


def _admin() -> User:
    u = User(id=uuid.uuid4(), email="a@x.com", full_name="A", is_active=True, is_platform_admin=True)
    u.created_at = datetime.now(timezone.utc)
    return u


def _app_and_service():
    settings = _settings()
    service = ApiKeyService(keys=InMemoryApiKeyRepo(), audit=InMemoryAudit())
    app = create_app(settings)

    async def _fake_user(request: Request) -> User:
        request.state.access_jti = "j"
        request.state.access_exp = 9999999999
        return _admin()

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_api_key_service] = lambda: service
    return app


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)


@pytest.mark.asyncio
async def test_create_list_revoke_flow() -> None:
    app = _app_and_service()
    async with _client(app) as client:
        created = await client.post(
            f"/api/v1/orgs/{_ORG}/api-keys",
            json={"name": "ci", "rate_limit_per_min": 50},
            headers={"Authorization": "Bearer x"},
        )
        assert created.status_code == 201, created.text
        body = created.json()["data"]
        assert body["api_key"].startswith("fk_live_")
        key_id = body["id"]

        listed = await client.get(
            f"/api/v1/orgs/{_ORG}/api-keys", headers={"Authorization": "Bearer x"}
        )
        assert listed.status_code == 200
        keys = listed.json()["data"]
        assert len(keys) == 1
        assert "api_key" not in keys[0]  # secret never returned on list

        revoked = await client.delete(
            f"/api/v1/orgs/{_ORG}/api-keys/{key_id}", headers={"Authorization": "Bearer x"}
        )
        assert revoked.status_code == 204
