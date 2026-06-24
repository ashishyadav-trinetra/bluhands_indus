"""Unit tests for TenantService.

All tests are offline — no database, no Redis. The service is wired with
in-memory fakes (InMemoryTenantRepo, InMemoryAudit) from tests/fakes.py.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.enums import Industry, IsolationLevel, TenantStatus
from app.schemas.tenant import TenantCreate
from app.services.tenant_service import TenantService
from tests.fakes import InMemoryAudit, InMemoryTenantRepo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ORG_A = uuid.uuid4()
ORG_B = uuid.uuid4()
ACTOR = f"user:{uuid.uuid4()}"


def _service() -> tuple[TenantService, InMemoryTenantRepo, InMemoryAudit]:
    repo = InMemoryTenantRepo()
    audit = InMemoryAudit()
    svc = TenantService(tenants=repo, audit=audit)
    return svc, repo, audit


def _create_payload(
    industry: Industry = Industry.ECOMMERCE,
    isolation_level: IsolationLevel = IsolationLevel.POOLED,
) -> TenantCreate:
    return TenantCreate(industry=industry, isolation_level=isolation_level)


# ---------------------------------------------------------------------------
# create_tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_tenant_happy_path() -> None:
    svc, repo, audit = _service()

    tenant = await svc.create_tenant(ORG_A, _create_payload(), actor=ACTOR, ip="1.2.3.4")

    assert tenant.id is not None
    assert tenant.org_id == ORG_A
    assert tenant.industry == Industry.ECOMMERCE
    assert tenant.isolation_level == IsolationLevel.POOLED
    assert tenant.status == TenantStatus.CREATED
    assert tenant.region == "us-east-1"

    # Persisted in repo
    assert await repo.get_by_id(tenant.id) is tenant

    # Audit event recorded
    assert "tenant.created" in audit.actions()
    event = audit.events[0]
    assert event.org_id == ORG_A
    assert event.tenant_id == tenant.id
    assert event.actor == ACTOR
    assert event.ip == "1.2.3.4"


@pytest.mark.asyncio
async def test_create_tenant_sets_display_name_and_region() -> None:
    svc, _, _ = _service()
    payload = TenantCreate(
        industry=Industry.CRM,
        display_name="My CRM",
        region="ap-south-1",
    )
    tenant = await svc.create_tenant(ORG_A, payload, actor=ACTOR)

    assert tenant.display_name == "My CRM"
    assert tenant.region == "ap-south-1"


@pytest.mark.asyncio
async def test_create_tenant_duplicate_industry_raises_conflict() -> None:
    svc, _, _ = _service()
    payload = _create_payload(Industry.ECOMMERCE)

    await svc.create_tenant(ORG_A, payload, actor=ACTOR)

    with pytest.raises(ConflictError, match="ecommerce"):
        await svc.create_tenant(ORG_A, payload, actor=ACTOR)


@pytest.mark.asyncio
async def test_create_tenant_same_industry_different_org_allowed() -> None:
    """Two orgs may each have a tenant for the same industry."""
    svc, _, _ = _service()
    payload = _create_payload(Industry.ECOMMERCE)

    t1 = await svc.create_tenant(ORG_A, payload, actor=ACTOR)
    t2 = await svc.create_tenant(ORG_B, payload, actor=ACTOR)

    assert t1.id != t2.id


@pytest.mark.asyncio
async def test_create_tenant_different_industries_same_org_allowed() -> None:
    svc, _, _ = _service()

    t1 = await svc.create_tenant(ORG_A, _create_payload(Industry.ECOMMERCE), actor=ACTOR)
    t2 = await svc.create_tenant(ORG_A, _create_payload(Industry.CRM), actor=ACTOR)

    assert t1.id != t2.id


@pytest.mark.asyncio
async def test_create_tenant_emits_no_extra_audit_events() -> None:
    svc, _, audit = _service()
    await svc.create_tenant(ORG_A, _create_payload(), actor=ACTOR)

    assert len(audit.events) == 1


# ---------------------------------------------------------------------------
# get_tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tenant_happy_path() -> None:
    svc, _, _ = _service()
    created = await svc.create_tenant(ORG_A, _create_payload(), actor=ACTOR)

    fetched = await svc.get_tenant(created.id, org_id=ORG_A)
    assert fetched is created


@pytest.mark.asyncio
async def test_get_tenant_not_found_raises() -> None:
    svc, _, _ = _service()

    with pytest.raises(NotFoundError):
        await svc.get_tenant(uuid.uuid4(), org_id=ORG_A)


@pytest.mark.asyncio
async def test_get_tenant_wrong_org_raises_not_found() -> None:
    """Org-id mismatch returns 404, not 403, to prevent enumeration."""
    svc, _, _ = _service()
    created = await svc.create_tenant(ORG_A, _create_payload(), actor=ACTOR)

    with pytest.raises(NotFoundError):
        await svc.get_tenant(created.id, org_id=ORG_B)


# ---------------------------------------------------------------------------
# list_tenants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tenants_returns_only_org_tenants() -> None:
    svc, _, _ = _service()

    await svc.create_tenant(ORG_A, _create_payload(Industry.ECOMMERCE), actor=ACTOR)
    await svc.create_tenant(ORG_A, _create_payload(Industry.CRM), actor=ACTOR)
    await svc.create_tenant(ORG_B, _create_payload(Industry.ECOMMERCE), actor=ACTOR)

    result = await svc.list_tenants(ORG_A)
    assert len(result) == 2
    assert all(t.org_id == ORG_A for t in result)


@pytest.mark.asyncio
async def test_list_tenants_empty_org() -> None:
    svc, _, _ = _service()
    result = await svc.list_tenants(ORG_A)
    assert result == []


@pytest.mark.asyncio
async def test_list_tenants_pagination() -> None:
    svc, _, _ = _service()
    industries = [Industry.ECOMMERCE, Industry.CRM, Industry.RESTAURANT]
    for ind in industries:
        await svc.create_tenant(ORG_A, _create_payload(ind), actor=ACTOR)

    page1 = await svc.list_tenants(ORG_A, skip=0, limit=2)
    page2 = await svc.list_tenants(ORG_A, skip=2, limit=2)

    assert len(page1) == 2
    assert len(page2) == 1
    # No overlap
    ids1 = {t.id for t in page1}
    ids2 = {t.id for t in page2}
    assert ids1.isdisjoint(ids2)
