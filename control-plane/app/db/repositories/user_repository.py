"""User repository (SQLAlchemy implementation)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Data access for ``User`` rows."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Return an active (non-deleted) user by id."""
        return await self.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Return a non-deleted user by exact email, or None."""
        stmt = select(User).where(
            User.email == email.lower(),
            User.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        """Return non-deleted users, newest first (for the admin panel)."""
        stmt = (
            select(User)
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
