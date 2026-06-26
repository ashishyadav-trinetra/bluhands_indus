"""Unit tests for Supabase JIT provisioning + self-heal of org-less users."""

from __future__ import annotations

import pytest

from app.db.models.user import User


@pytest.mark.asyncio
async def test_new_user_gets_org_and_membership(auth_components) -> None:
    service = auth_components["service"]
    memberships = auth_components["memberships"]

    user = await service.provision_from_supabase(
        external_id="sub-new", email="New@Example.com", full_name="New User"
    )
    ms = await memberships.list_for_user(user.id)
    assert len(ms) == 1  # org + owner membership created
    assert user.email == "new@example.com"


@pytest.mark.asyncio
async def test_existing_user_without_membership_is_backfilled(auth_components) -> None:
    service = auth_components["service"]
    users = auth_components["users"]
    memberships = auth_components["memberships"]

    # A user that exists but has NO membership (created before provisioning).
    existing = User(
        email="stuck@example.com",
        full_name="Stuck",
        password_hash=None,
        is_active=True,
        is_platform_admin=False,
    )
    await users.add(existing)
    assert await memberships.list_for_user(existing.id) == []

    result = await service.provision_from_supabase(
        external_id="sub-stuck", email="stuck@example.com"
    )
    assert result.id == existing.id
    assert result.external_id == "sub-stuck"  # backfilled
    assert len(await memberships.list_for_user(existing.id)) == 1  # org back-filled


@pytest.mark.asyncio
async def test_existing_user_with_membership_is_not_duplicated(auth_components) -> None:
    service = auth_components["service"]
    memberships = auth_components["memberships"]

    user = await service.provision_from_supabase(external_id="s1", email="dup@example.com")
    before = len(await memberships.list_for_user(user.id))
    await service.provision_from_supabase(external_id="s1", email="dup@example.com")
    after = len(await memberships.list_for_user(user.id))
    assert before == after == 1  # no duplicate org on second login
