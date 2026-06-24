"""Smoke tests for the Faker factories."""

from __future__ import annotations

import uuid

from app.db.models.enums import BuildStatus, Industry
from tests.factories import make_build_run, make_organization, make_tenant, make_user


def test_make_user_unique_and_complete() -> None:
    u1, u2 = make_user(), make_user()
    assert u1.email != u2.email
    assert u1.id and u1.created_at and u1.is_active is True


def test_make_org_and_tenant_link() -> None:
    org = make_organization()
    tenant = make_tenant(org.id, industry=Industry.CRM)
    assert tenant.org_id == org.id
    assert tenant.industry is Industry.CRM


def test_make_build_run_defaults() -> None:
    tid = uuid.uuid4()
    b = make_build_run(tid)
    assert b.tenant_id == tid
    assert b.status is BuildStatus.QUEUED
    assert b.credits_cost == 10
