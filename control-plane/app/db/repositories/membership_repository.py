"""Membership repository (SQLAlchemy implementation)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.membership import Membership
from app.db.repositories.base import BaseRepository


class MembershipRepository(BaseRepository[Membership]):
    """Data access for ``Membership`` rows."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Membership)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Membership]:
        """Return a user's active memberships with organizations eager-loaded."""
        stmt = (
            select(Membership)
            .where(Membership.user_id == user_id, Membership.deleted_at.is_(None))
            .options(selectinload(Membership.organization))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_user_org(
        self, user_id: uuid.UUID, org_id: uuid.UUID
    ) -> Membership | None:
        """Return a user's membership in a specific org, or None."""
        stmt = select(Membership).where(
            Membership.user_id == user_id,
            Membership.org_id == org_id,
            Membership.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
