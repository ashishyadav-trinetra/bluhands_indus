"""Unit tests for per-role LLM gating + the admin role-change service."""

from __future__ import annotations

import uuid

import pytest

from app.core.config import Settings
from app.db.models.enums import PlatformRole
from app.services.admin_service import AdminService


def test_model_for_role_maps_tester_and_self() -> None:
    s = Settings(model_default="d", model_tester="t", model_self="se")
    assert s.model_for_role("tester") == "t"
    assert s.model_for_role("self") == "se"
    assert s.model_for_role("user") == "d"
    assert s.model_for_role("admin") == "d"
    assert s.model_for_role("unknown") == "d"  # safe default


class _FakeUser:
    def __init__(self, uid: uuid.UUID) -> None:
        self.id = uid
        self.platform_role = "user"
        self.is_platform_admin = False


class _FakeUsers:
    def __init__(self, user: _FakeUser | None) -> None:
        self._user = user

    async def get_by_id(self, uid: uuid.UUID):
        return self._user if (self._user and uid == self._user.id) else None


class _FakeAudit:
    def __init__(self) -> None:
        self.events: list = []

    async def record(self, event) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_set_role_promotes_to_admin_and_sets_flag() -> None:
    uid = uuid.uuid4()
    svc = AdminService(users=_FakeUsers(_FakeUser(uid)), audit=_FakeAudit())
    updated = await svc.set_role(uid, PlatformRole.ADMIN, actor="user:x")
    assert updated.platform_role == "admin"
    assert updated.is_platform_admin is True


@pytest.mark.asyncio
async def test_set_role_tester_does_not_set_admin_flag() -> None:
    uid = uuid.uuid4()
    svc = AdminService(users=_FakeUsers(_FakeUser(uid)), audit=_FakeAudit())
    updated = await svc.set_role(uid, PlatformRole.TESTER, actor="user:x")
    assert updated.platform_role == "tester"
    assert updated.is_platform_admin is False


@pytest.mark.asyncio
async def test_set_role_missing_user_raises() -> None:
    from app.core.exceptions import NotFoundError

    svc = AdminService(users=_FakeUsers(None), audit=_FakeAudit())
    with pytest.raises(NotFoundError):
        await svc.set_role(uuid.uuid4(), PlatformRole.ADMIN, actor="user:x")
