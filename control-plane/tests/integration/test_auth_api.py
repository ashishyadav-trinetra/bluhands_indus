"""Integration tests for the auth HTTP layer (ASGI, offline)."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import Request

from app.api.v1.dependencies.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db_session

BASE = "http://test"
REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"

_PAYLOAD = {
    "email": "owner@example.com",
    "password": "sup3rsecret",
    "full_name": "Owner",
    "organization_name": "Acme",
}


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)


@pytest.mark.asyncio
async def test_register_returns_token_and_sets_refresh_cookie(auth_app) -> None:
    async with _client(auth_app) as client:
        resp = await client.post(REGISTER, json=_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["access_token"]
    assert body["data"]["token_type"] == "bearer"
    assert "forge_refresh" in resp.headers.get("set-cookie", "")
    assert "httponly" in resp.headers.get("set-cookie", "").lower()


@pytest.mark.asyncio
async def test_login_success_after_register(auth_app) -> None:
    async with _client(auth_app) as client:
        await client.post(REGISTER, json=_PAYLOAD)
        resp = await client.post(
            LOGIN, json={"email": _PAYLOAD["email"], "password": _PAYLOAD["password"]}
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401_envelope(auth_app) -> None:
    async with _client(auth_app) as client:
        await client.post(REGISTER, json=_PAYLOAD)
        resp = await client.post(
            LOGIN, json={"email": _PAYLOAD["email"], "password": "nope-wrong"}
        )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHENTICATED"
    assert "request_id" in body


@pytest.mark.asyncio
async def test_duplicate_register_returns_409(auth_app) -> None:
    async with _client(auth_app) as client:
        await client.post(REGISTER, json=_PAYLOAD)
        resp = await client.post(REGISTER, json=_PAYLOAD)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_register_validation_error_returns_422(auth_app) -> None:
    bad = {**_PAYLOAD, "password": "short"}  # < 8 chars
    async with _client(auth_app) as client:
        resp = await client.post(REGISTER, json=bad)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_refresh_rotates_with_cookie(auth_app) -> None:
    async with _client(auth_app) as client:
        reg = await client.post(REGISTER, json=_PAYLOAD)
        first_access = reg.json()["data"]["access_token"]
        # The refresh cookie is stored in the client jar and resent.
        resp = await client.post(REFRESH)
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]
    assert resp.json()["data"]["access_token"] != first_access


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(auth_app) -> None:
    async with _client(auth_app) as client:
        resp = await client.post(REFRESH)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_and_logout_with_authenticated_user(auth_app) -> None:
    seeded = User(
        id=uuid.uuid4(),
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
        is_platform_admin=False,
    )
    seeded.created_at = datetime.now(timezone.utc)

    async def _fake_current_user(request: Request) -> User:
        request.state.access_jti = "access-jti-test"
        request.state.access_exp = int(time.time()) + 900
        return seeded

    async def _fake_db():
        from tests.conftest import FakeSession

        yield FakeSession()

    auth_app.dependency_overrides[get_current_user] = _fake_current_user
    auth_app.dependency_overrides[get_db_session] = _fake_db

    async with _client(auth_app) as client:
        me_resp = await client.get(ME, headers={"Authorization": "Bearer x"})
        logout_resp = await client.post(LOGOUT, headers={"Authorization": "Bearer x"})

    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["user"]["email"] == "owner@example.com"
    assert me_resp.json()["data"]["memberships"] == []
    assert logout_resp.status_code == 204
