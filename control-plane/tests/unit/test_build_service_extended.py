"""Unit tests for BuildService — list, cancel, approve methods.

Extends test_build_service.py without touching it.
All tests are offline; no DB, Celery, or network.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.build_run import BuildRun
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


def _payload() -> BuildStartRequest:
    return BuildStartRequest(prompt="Build a storefront with product listings and cart.")


async def _started_build(svc, tenants, org_id=ORG_A) -> tuple[BuildRun, Tenant]:
    tenant = await tenants.create(_tenant(org_id=org_id))
    build = await svc.start_build(tenant.id, org_id, _payload(), actor=ACTOR)
    return build, tenant


# ---------------------------------------------------------------------------
# list_builds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_builds_returns_empty_for_new_tenant() -> None:
    svc, _, tenants, _, _ = _service()
    tenant = await tenants.create(_tenant())
    result = await svc.list_builds(tenant.id, ORG_A)
    assert result == []


@pytest.mark.asyncio
async def test_list_builds_returns_started_builds() -> None:
    svc, _, tenants, _, _ = _service()
    build, tenant = await _started_build(svc, tenants)
    result = await svc.list_builds(tenant.id, ORG_A)
    assert len(result) == 1
    assert result[0].id == build.id


@pytest.mark.asyncio
async def test_list_builds_wrong_org_raises_not_found() -> None:
    svc, _, tenants, _, _ = _service()
    _, tenant = await _started_build(svc, tenants, org_id=ORG_A)
    with pytest.raises(NotFoundError):
        await svc.list_builds(tenant.id, ORG_B)


@pytest.mark.asyncio
async def test_list_builds_pagination() -> None:
    svc, _, tenants, _, _ = _service()
    tenant = await tenants.create(_tenant())
    for _ in range(3):
        await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR)
    page1 = await svc.list_builds(tenant.id, ORG_A, skip=0, limit=2)
    page2 = await svc.list_builds(tenant.id, ORG_A, skip=2, limit=2)
    assert len(page1) == 2
    assert len(page2) == 1


# ---------------------------------------------------------------------------
# cancel_build
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_build_transitions_to_cancelled() -> None:
    svc, _, tenants, _, _ = _service()
    build, tenant = await _started_build(svc, tenants)
    result = await svc.cancel_build(build.id, tenant.id, ORG_A, actor=ACTOR)
    assert result.status == BuildStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_build_emits_audit_event() -> None:
    svc, _, tenants, _, audit = _service()
    build, tenant = await _started_build(svc, tenants)
    await svc.cancel_build(build.id, tenant.id, ORG_A, actor=ACTOR)
    assert "build.cancelled" in audit.actions()


@pytest.mark.asyncio
async def test_cancel_already_failed_build_raises_validation_error() -> None:
    svc, builds, tenants, _, _ = _service()
    build, tenant = await _started_build(svc, tenants)
    await builds.transition(build, to_status=BuildStatus.FAILED)
    with pytest.raises(ValidationError, match="terminal"):
        await svc.cancel_build(build.id, tenant.id, ORG_A, actor=ACTOR)


@pytest.mark.asyncio
async def test_cancel_live_build_raises_validation_error() -> None:
    svc, builds, tenants, _, _ = _service()
    build, tenant = await _started_build(svc, tenants)
    await builds.transition(build, to_status=BuildStatus.LIVE)
    with pytest.raises(ValidationError):
        await svc.cancel_build(build.id, tenant.id, ORG_A, actor=ACTOR)


@pytest.mark.asyncio
async def test_cancel_build_not_found_raises() -> None:
    svc, _, tenants, _, _ = _service()
    tenant = await tenants.create(_tenant())
    with pytest.raises(NotFoundError):
        await svc.cancel_build(uuid.uuid4(), tenant.id, ORG_A, actor=ACTOR)


# ---------------------------------------------------------------------------
# approve_build
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_build_transitions_to_live() -> None:
    svc, builds, tenants, _, _ = _service()
    build, tenant = await _started_build(svc, tenants)
    await builds.transition(build, to_status=BuildStatus.REVIEW)
    result = await svc.approve_build(build.id, tenant.id, ORG_A, actor=ACTOR)
    assert result.status == BuildStatus.LIVE


@pytest.mark.asyncio
async def test_approve_build_emits_audit_event() -> None:
    svc, builds, tenants, _, audit = _service()
    build, tenant = await _started_build(svc, tenants)
    await builds.transition(build, to_status=BuildStatus.REVIEW)
    await svc.approve_build(build.id, tenant.id, ORG_A, actor=ACTOR)
    assert "build.approved" in audit.actions()


@pytest.mark.asyncio
async def test_approve_non_review_build_raises_validation_error() -> None:
    svc, _, tenants, _, _ = _service()
    build, tenant = await _started_build(svc, tenants)
    # build is QUEUED, not REVIEW
    with pytest.raises(ValidationError, match="REVIEW"):
        await svc.approve_build(build.id, tenant.id, ORG_A, actor=ACTOR)


@pytest.mark.asyncio
async def test_approve_wrong_org_raises_not_found() -> None:
    svc, builds, tenants, _, _ = _service()
    build, tenant = await _started_build(svc, tenants, org_id=ORG_A)
    await builds.transition(build, to_status=BuildStatus.REVIEW)
    with pytest.raises(NotFoundError):
        await svc.approve_build(build.id, tenant.id, ORG_B, actor=ACTOR)


@pytest.mark.asyncio
async def test_approve_build_captures_credits() -> None:
    """approve_build must call credits.capture exactly once."""
    builds = InMemoryBuildRunRepo()
    tenants = InMemoryTenantRepo()
    credits = FakeCreditService()
    audit = InMemoryAudit()
    svc = BuildService(
        builds=builds, tenants=tenants,
        dispatcher=FakeBuildDispatcher(), credits=credits, audit=audit,
    )
    build, tenant = await _started_build(svc, tenants)
    await builds.transition(build, to_status=BuildStatus.REVIEW)

    await svc.approve_build(build.id, tenant.id, ORG_A, actor=ACTOR)

    assert len(credits.captures) == 1
    assert credits.captures[0]["build_run_id"] == build.id


@pytest.mark.asyncio
async def test_start_build_reserves_credits() -> None:
    """start_build must reserve credits from the org wallet."""
    builds = InMemoryBuildRunRepo()
    tenants = InMemoryTenantRepo()
    credits = FakeCreditService()
    audit = InMemoryAudit()
    svc = BuildService(
        builds=builds, tenants=tenants,
        dispatcher=FakeBuildDispatcher(), credits=credits, audit=audit,
    )
    tenant = await tenants.create(_tenant())

    build = await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR)

    assert len(credits.reserves) == 1
    assert credits.reserves[0]["org_id"] == ORG_A
    assert credits.reserves[0]["build_run_id"] == build.id


@pytest.mark.asyncio
async def test_start_build_insufficient_credits_does_not_dispatch() -> None:
    """If credits.reserve raises, no Celery task must be enqueued."""
    from app.core.exceptions import InsufficientCreditsError

    builds = InMemoryBuildRunRepo()
    tenants = InMemoryTenantRepo()
    credits = FakeCreditService(insufficient=True)
    dispatcher = FakeBuildDispatcher()
    audit = InMemoryAudit()
    svc = BuildService(
        builds=builds, tenants=tenants,
        dispatcher=dispatcher, credits=credits, audit=audit,
    )
    tenant = await tenants.create(_tenant())

    with pytest.raises(InsufficientCreditsError):
        await svc.start_build(tenant.id, ORG_A, _payload(), actor=ACTOR)

    assert len(dispatcher.dispatched) == 0
