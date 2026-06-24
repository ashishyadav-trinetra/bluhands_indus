"""Organization repository (SQLAlchemy implementation)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Organization
from app.db.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Data access for ``Organization`` rows."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Organization)
