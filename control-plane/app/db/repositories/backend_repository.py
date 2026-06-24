"""BackendRepository — reads provisioned backend records for a tenant."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.backend import Backend
from app.db.models.enums import BackendStatus
from app.db.repositories.base import BaseRepository


class BackendRepository(BaseRepository[Backend]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Backend)

    async def get_active_for_tenant(self, tenant_id: uuid.UUID) -> Backend | None:
        """Return the first active (READY) backend for a tenant, or None."""
        stmt = (
            select(Backend)
            .where(
                Backend.tenant_id == tenant_id,
                Backend.status == BackendStatus.READY,
                Backend.deleted_at.is_(None),
            )
            .order_by(Backend.created_at.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
