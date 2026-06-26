"""Unit tests for AdminService.delete_user (soft-delete, no self-delete)."""

from __future__ import annotations

import types
import uuid

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.services.admin_service import AdminService


class _Users:
    def __init__(self, user) -> None:
        self._user = user

    async def get_by_id(self, uid):
        return self._user if (self._user and uid == self._user.id) else None


class _Audit:
    def __init__(self) -> None:
        self.events: list = []

    async def record(self, event) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_delete_user_soft_deletes() -> None:
    uid = uuid.uuid4()
    user = types.SimpleNamespace(id=uid, is_active=True, deleted_at=None)
    svc = AdminService(users=_Users(user), audit=_Audit())
    await svc.delete_user(uid, acting_user_id=uuid.uuid4(), actor="user:x")
    assert user.is_active is False
    assert user.deleted_at is not None


@pytest.mark.asyncio
async def test_cannot_delete_self() -> None:
    uid = uuid.uuid4()
    svc = AdminService(users=_Users(None), audit=_Audit())
    with pytest.raises(ValidationError):
        await svc.delete_user(uid, acting_user_id=uid, actor="user:x")


@pytest.mark.asyncio
async def test_delete_missing_user_raises() -> None:
    svc = AdminService(users=_Users(None), audit=_Audit())
    with pytest.raises(NotFoundError):
        await svc.delete_user(uuid.uuid4(), acting_user_id=uuid.uuid4(), actor="user:x")
