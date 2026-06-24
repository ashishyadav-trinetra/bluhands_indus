"""Integration tests for the tenants HTTP layer (ASGI, offline)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

from app.api.v1.dependencies.auth import get_current_user
from app.api.v1.dependencies.services import get_tenant_service
from app.db.models.user import User
from app.services.tenant_service import TenantService
from tests.fakes import InMemoryAudit, InMemoryTenantRepo

BASE = "http://test"
ORG_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_user() -> User:
    user = User(
        email="admin@forge.internal",
        full_name="Admin",
        password_hash="x",
        is_active=True,
        is_platform_admin=True,
    )
    user.id = uuid.uuid4()
    return user


def _regular_user() -> User:
    user = User(
        email="member@example.com",
        full_name="Member",
        password_hash="x",
        is_active=True,
        is_platform_admin=False,
    )
    user.id = uuid.uuid4()
    return user


def _tenant_service() -> TenantService:
    return TenantService(tenants=InMemoryTenantRepo(), audit=InMemoryAudit())


def _tenant_app(settings, *, user: User | None = None, service: TenantService | None = None):
    """Build a test ASGI app with auth + tenant service overridden."""
    from app.main import create_app

    resolved_user = user if user is not None else _admin_user()
    resolved_service = service if service is not None else _tenant_service()

    app = create_app(settings)
    app.dependency_overrides[get_current_user] = lambda: resolved_user
    app.dependency_overrides[get_tenant_service] = lambda: resolved_service
    return app


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)


def _url(org_id: uuid.UUID = ORG_ID, suffix: str = "") -> str:
    return f"/api/v1/orgs/{org_id}/tenants{suffix}"


_CREATE_PAYLOAD = {
    "industry": "ecommerce",
    "isolation_level": "pooled",
    "display_name": "My Shop",
    "region": "us-east-1",
}


# ---------------------------------------------------------------------------
# POST /api/v1/orgs/{org_id}/tenants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_tenant_returns_201(settings) -> None:
    async with _client(_tenant_app(settings)) as client:
        resp = await client.post(_url(), json=_CREATE_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["industry"] == "ecommerce"
    assert data["isolation_level"] == "pooled"
    assert data["display_name"] == "My Shop"
    assert data["region"] == "us-east-1"
    assert data["org_id"] == str(ORG_ID)
    assert uuid.UUID(data["id"])
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_create_tenant_duplicate_industry_returns_409(settings) -> None:
    service = _tenant_service()
    async with _client(_tenant_app(settings, service=service)) as client:
        await client.post(_url(), json=_CREATE_PAYLOAD)
        resp = await client.post(_url(), json=_CREATE_PAYLOAD)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_create_tenant_invalid_industry_returns_422(settings) -> None:
    payload = {**_CREATE_PAYLOAD, "industry": "not_a_real_industry"}
    async with _client(_tenant_app(settings)) as client:
        resp = await client.post(_url(), json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_tenant_rbac_denied_for_non_member(settings) -> None:
    """A non-member (no org membership, not platform admin) gets 403."""
    from app.db.session import get_db_session
    from tests.conftest import FakeSession

    viewer = _regular_user()
    app = _tenant_app(settings, user=viewer)

    # Inject a DB session that returns no membership (scalar_one_or_none → None)
    async def _no_membership() -> AsyncIterator:
        yield FakeSession()

    app.dependency_overrides[get_db_session] = _no_membership

    async with _client(app) as client:
        resp = await client.post(_url(), json=_CREATE_PAYLOAD)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/tenants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tenants_empty(settings) -> None:
    async with _client(_tenant_app(settings)) as client:
        resp = await client.get(_url())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == []


@pytest.mark.asyncio
async def test_list_tenants_returns_created_tenant(settings) -> None:
    service = _tenant_service()
    async with _client(_tenant_app(settings, service=service)) as client:
        await client.post(_url(), json=_CREATE_PAYLOAD)
        resp = await client.get(_url())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["industry"] == "ecommerce"


@pytest.mark.asyncio
async def test_list_tenants_pagination(settings) -> None:
    service = _tenant_service()
    industries = ["ecommerce", "crm", "restaurant"]
    async with _client(_tenant_app(settings, service=service)) as client:
        for ind in industries:
            await client.post(_url(), json={**_CREATE_PAYLOAD, "industry": ind})
        resp1 = await client.get(_url(), params={"skip": 0, "limit": 2})
        resp2 = await client.get(_url(), params={"skip": 2, "limit": 2})
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert len(resp1.json()["data"]) == 2
    assert len(resp2.json()["data"]) == 1


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/tenants/{tenant_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tenant_happy_path(settings) -> None:
    service = _tenant_service()
    async with _client(_tenant_app(settings, service=service)) as client:
        created = (await client.post(_url(), json=_CREATE_PAYLOAD)).json()["data"]
        resp = await client.get(_url(suffix=f"/{created['id']}"))
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_tenant_not_found_returns_404(settings) -> None:
    async with _client(_tenant_app(settings)) as client:
        resp = await client.get(_url(suffix=f"/{uuid.uuid4()}"))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_get_tenant_wrong_org_returns_404(settings) -> None:
    """Tenant belonging to a different org returns 404 (prevents enumeration)."""
    service = _tenant_service()
    other_org = uuid.uuid4()

    async with _client(_tenant_app(settings, service=service)) as client:
        created = (await client.post(_url(), json=_CREATE_PAYLOAD)).json()["data"]
        resp = await client.get(_url(org_id=other_org, suffix=f"/{created['id']}"))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_tenant_invalid_uuid_returns_422(settings) -> None:
    async with _client(_tenant_app(settings)) as client:
        resp = await client.get(_url(suffix="/not-a-uuid"))
    assert resp.status_code == 422
