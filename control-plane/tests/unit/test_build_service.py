"""Unit tests for BuildService.start_build.

All tests are offline — no database, no Celery broker. Dependencies are
wired with in-memory fakes from tests/fakes.py.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import NotFoundError
from app.db.models.enums import BuildStatus, Industry, IsolationLevel, TenantStatus
from app.db.models.tenant import Tenant
from app.schemas.build import BuildStartRequest
from app.services.build_service import BuildService
from tests.fakes import (
    FakeBuildDispatcher,
    FakeCreditService,
    InMemoryAudit,
    InMemoryBuildRunRepo,
    InMemoryTenantRepo,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ORG_A = uuid.uuid4()
ORG_B = uuid.uuid4()
ACTOR = f"user:{uuid.uuid4()}"


def _tenant(org_id: uuid.UUID = ORG_A) -> Tenant:
    t = Tenant(
        org_id=org_id,
        industry=Industry.ECOMMERCE,
        isolation_level=IsolationLevel.POOLED,
        status=TenantStatus.ACTIVE,
        region="us-east-1",
    )
    t.id = uuid.uuid4()
    return t


def _service() -> tuple[BuildService, InMemoryBuildRunRepo, InMemoryTenantRepo, FakeBuildDispatcher, InMemoryAudit]:
    builds = InMemoryBuildRunRepo()
    tenants = InMemoryTenantRepo()
    dispatcher = FakeBuildDispatcher()
    credits = FakeCreditService()
    audit = InMemoryAudit()
    svc = BuildService(builds=builds, tenants=tenants, dispatcher=dispatcher, credits=credits, audit=audit)
    return svc, builds, tenants, dispatcher, audit


def _payload(prompt: str = "Build a storefront with product listings and cart.") -> BuildStartRequest:
    return BuildStartRequest(prompt=prompt)


# ---------------------------------------------------------------------------
# start_build — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_build_returns_queued_build_run() -> None:
    svc, builds, tenants, dispatcher, audit = _service()
    tenant = await tenants.create(_tenant())

    build = await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR)

    assert build.id is not None
    assert build.tenant_id == tenant.id
    assert build.status == BuildStatus.QUEUED
    assert build.prompt == "Build a storefront with product listings and cart."
    assert build.credits_cost == 10  # default build_credit_cost


@pytest.mark.asyncio
async def test_start_build_sets_celery_task_id() -> None:
    svc, _, tenants, dispatcher, _ = _service()
    tenant = await tenants.create(_tenant())

    build = await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR)

    assert build.celery_task_id == f"build:{build.id}"


@pytest.mark.asyncio
async def test_start_build_enqueues_on_default_queue() -> None:
    svc, _, tenants, dispatcher, _ = _service()
    tenant = await tenants.create(_tenant())

    build = await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR)

    assert len(dispatcher.dispatched) == 1
    assert dispatcher.dispatched[0]["queue"] == "default"
    assert dispatcher.dispatched[0]["build_id"] == build.id


@pytest.mark.asyncio
async def test_start_build_persists_to_repo() -> None:
    svc, builds, tenants, _, _ = _service()
    tenant = await tenants.create(_tenant())

    build = await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR)

    assert await builds.get_by_id(build.id) is build


@pytest.mark.asyncio
async def test_start_build_emits_audit_event() -> None:
    svc, _, tenants, _, audit = _service()
    tenant = await tenants.create(_tenant())

    await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR, ip="10.0.0.1")

    assert "build.started" in audit.actions()
    event = audit.events[0]
    assert event.org_id == ORG_A
    assert event.tenant_id == tenant.id
    assert event.actor == ACTOR
    assert event.ip == "10.0.0.1"


@pytest.mark.asyncio
async def test_start_build_deterministic_task_id_format() -> None:
    """Task ID must be 'build:<uuid>' — used for broker-level dedup."""
    svc, _, tenants, dispatcher, _ = _service()
    tenant = await tenants.create(_tenant())

    build = await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR)

    assert build.celery_task_id == f"build:{build.id}"
    assert dispatcher.dispatched[0]["task_id"] == f"build:{build.id}"


# ---------------------------------------------------------------------------
# start_build — error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_build_unknown_tenant_raises_not_found() -> None:
    svc, _, _, _, _ = _service()

    with pytest.raises(NotFoundError):
        await svc.start_build(uuid.uuid4(), ORG_A, _payload(), actor=ACTOR)


@pytest.mark.asyncio
async def test_start_build_wrong_org_raises_not_found() -> None:
    """Tenant belonging to ORG_B cannot be started under ORG_A."""
    svc, _, tenants, _, _ = _service()
    tenant = await tenants.create(_tenant(org_id=ORG_B))

    with pytest.raises(NotFoundError):
        await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR)


@pytest.mark.asyncio
async def test_start_build_no_dispatch_on_tenant_not_found() -> None:
    """Dispatcher must NOT be called if tenant validation fails."""
    svc, _, _, dispatcher, _ = _service()

    with pytest.raises(NotFoundError):
        await svc.start_build(uuid.uuid4(), ORG_A, _payload(), actor=ACTOR)

    assert len(dispatcher.dispatched) == 0


# ---------------------------------------------------------------------------
# get_build
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_build_happy_path() -> None:
    svc, _, tenants, _, _ = _service()
    tenant = await tenants.create(_tenant())
    started = await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR)

    fetched = await svc.get_build(started.id, tenant_id=tenant.id)
    assert fetched is started


@pytest.mark.asyncio
async def test_get_build_not_found_raises() -> None:
    svc, _, _, _, _ = _service()

    with pytest.raises(NotFoundError):
        await svc.get_build(uuid.uuid4(), tenant_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_get_build_wrong_tenant_raises_not_found() -> None:
    svc, _, tenants, _, _ = _service()
    tenant = await tenants.create(_tenant())
    started = await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR)

    with pytest.raises(NotFoundError):
        await svc.get_build(started.id, tenant_id=uuid.uuid4())
