"""Faker-based test-data factories.

Produce ready-to-use ORM model instances (ids + timestamps stamped, as a DB
would) for use across unit/integration tests. Keep these deterministic-friendly:
pass overrides for any field you assert on.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from faker import Faker

from app.db.models.build_run import BuildRun
from app.db.models.enums import (
    BuildStatus,
    Industry,
    IsolationLevel,
    OrgPlan,
    TenantStatus,
)
from app.db.models.organization import Organization
from app.db.models.tenant import Tenant
from app.db.models.user import User

faker = Faker()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_user(**overrides) -> User:
    """Build a User with sensible defaults."""
    data = dict(
        id=uuid.uuid4(),
        email=faker.unique.email(),
        full_name=faker.name(),
        password_hash=None,
        is_active=True,
        is_platform_admin=False,
    )
    data.update(overrides)
    user = User(**data)
    user.created_at = overrides.get("created_at", _now())
    return user


def make_organization(**overrides) -> Organization:
    """Build an Organization with sensible defaults."""
    data = dict(id=uuid.uuid4(), name=faker.company(), plan=OrgPlan.FREE, status="active")
    data.update(overrides)
    org = Organization(**data)
    org.created_at = overrides.get("created_at", _now())
    return org


def make_tenant(org_id: uuid.UUID | None = None, **overrides) -> Tenant:
    """Build a Tenant with sensible defaults."""
    data = dict(
        id=uuid.uuid4(),
        org_id=org_id or uuid.uuid4(),
        industry=Industry.ECOMMERCE,
        isolation_level=IsolationLevel.POOLED,
        status=TenantStatus.CREATED,
        region="ap-south-1",
        display_name=faker.company(),
    )
    data.update(overrides)
    tenant = Tenant(**data)
    tenant.created_at = overrides.get("created_at", _now())
    tenant.updated_at = overrides.get("updated_at", _now())
    return tenant


def make_build_run(tenant_id: uuid.UUID | None = None, **overrides) -> BuildRun:
    """Build a BuildRun with sensible defaults."""
    data = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        status=BuildStatus.QUEUED,
        credits_cost=10,
    )
    data.update(overrides)
    build = BuildRun(**data)
    build.created_at = overrides.get("created_at", _now())
    return build
