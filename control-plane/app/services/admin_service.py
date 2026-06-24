"""Admin business logic: list users, list orgs, and change a user's platform role.

Single responsibility: platform-admin user management. Depends on the user
repository + audit logger (injected). Changing someone to ``ADMIN`` also sets the
``is_platform_admin`` flag the RBAC layer checks (defense in depth).
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.db.models.audit import AuditEvent
from app.db.models.enums import PlatformRole
from app.db.models.organization import Organization
from app.db.models.user import User
from app.services.protocols import AuditLoggerProtocol


class UserRepositoryProtocol(Protocol):
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...
    async def list_all(self, *, limit: int, offset: int) -> list[User]: ...


class OrganizationRepositoryProtocol(Protocol):
    async def list(self, limit: int, offset: int) -> list[Organization]: ...


class AdminService:
    """Coordinates platform-admin user and organisation operations."""

    def __init__(
        self,
        *,
        users: UserRepositoryProtocol,
        audit: AuditLoggerProtocol,
        orgs: OrganizationRepositoryProtocol | None = None,
    ) -> None:
        self._users = users
        self._audit = audit
        self._orgs = orgs

    async def list_users(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        """Return platform users for the admin panel (newest first)."""
        return await self._users.list_all(limit=limit, offset=offset)

    async def list_orgs(self, *, limit: int = 100, offset: int = 0) -> list[Organization]:
        """Return all organisations (admin panel)."""
        if self._orgs is None:
            raise RuntimeError("AdminService requires orgs repository to list organisations")
        return await self._orgs.list(limit=limit, offset=offset)

    async def set_role(
        self,
        user_id: uuid.UUID,
        role: PlatformRole,
        *,
        actor: str,
        ip: str | None = None,
    ) -> User:
        """Set a user's platform role. Keeps ``is_platform_admin`` in sync.

        Raises:
            NotFoundError: if the user does not exist.
        """
        from app.core.exceptions import NotFoundError

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")

        previous = user.platform_role
        user.platform_role = role.value
        user.is_platform_admin = role is PlatformRole.ADMIN

        await self._audit.record(
            AuditEvent(
                actor=actor,
                action="admin.set_role",
                target=str(user_id),
                ip=ip,
                event_metadata={"from": previous, "to": role.value},
            )
        )
        return user
