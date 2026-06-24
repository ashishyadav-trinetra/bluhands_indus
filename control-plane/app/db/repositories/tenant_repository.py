"""TenantRepository — concrete async repository for the Tenant model.

Depends only on SQLAlchemy AsyncSession; the service layer references it via
TenantRepositoryProtocol so it can be swapped for an in-memory fake in tests.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import Industry
from app.db.models.tenant import Tenant
from app.db.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    """CRUD + domain queries for tenants."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Tenant)

    async def create(self, tenant: Tenant) -> Tenant:
        """Persist a new tenant and flush to obtain server defaults."""
        return await self.add(tenant)

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        """Return a non-deleted tenant by primary key, or None."""
        return await self.get(tenant_id)

    async def list_for_org(
        self, org_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> list[Tenant]:
        """Return non-deleted tenants for an organisation, newest first."""
        stmt = (
            select(Tenant)
            .where(Tenant.org_id == org_id, Tenant.deleted_at.is_(None))
            .order_by(Tenant.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_org_and_industry(
        self, org_id: uuid.UUID, industry: Industry
    ) -> Tenant | None:
        """Return the active tenant for a given org+industry pair, or None.

        Used to enforce the one-tenant-per-industry-per-org constraint before
        inserting, which gives a cleaner error than a DB unique violation.
        """
        stmt = select(Tenant).where(
            Tenant.org_id == org_id,
            Tenant.industry == industry,
            Tenant.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
