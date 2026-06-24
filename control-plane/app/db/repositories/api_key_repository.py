"""API key repository — create, lookup by hash, list, fetch by id."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.api_key import ApiKey


class ApiKeyRepository:
    """Data access for ``ApiKey`` rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, key: ApiKey) -> ApiKey:
        self._session.add(key)
        await self._session.flush()
        return key

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, key_id: uuid.UUID) -> ApiKey | None:
        return await self._session.get(ApiKey, key_id)

    async def list_for_org(self, org_id: uuid.UUID) -> list[ApiKey]:
        stmt = select(ApiKey).where(ApiKey.org_id == org_id).order_by(ApiKey.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
