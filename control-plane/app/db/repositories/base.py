"""Generic async repository (Repository Pattern).

The service layer depends on repositories, never on raw SQL. This base provides
common CRUD with soft-delete awareness; concrete repositories subclass it and
add domain-specific queries.
"""

from __future__ import annotations

import uuid
from datetime import timezone
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """CRUD operations shared by all repositories.

    Args:
        session: The request-scoped async session.
        model: The ORM model class this repository manages.
    """

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self._session = session
        self._model = model

    async def get(self, entity_id: uuid.UUID, *, include_deleted: bool = False) -> ModelT | None:
        """Return an entity by id, excluding soft-deleted rows by default."""
        entity = await self._session.get(self._model, entity_id)
        if entity is None:
            return None
        if (
            not include_deleted
            and isinstance(entity, SoftDeleteMixin)
            and entity.is_deleted
        ):
            return None
        return entity

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[ModelT]:
        """Return a page of non-deleted entities (offset pagination)."""
        stmt = select(self._model).limit(limit).offset(offset)
        if issubclass(self._model, SoftDeleteMixin):
            stmt = stmt.where(self._model.deleted_at.is_(None))  # type: ignore[attr-defined]
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, entity: ModelT) -> ModelT:
        """Stage a new entity and flush to obtain server defaults/ids."""
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def soft_delete(self, entity: ModelT) -> None:
        """Mark an entity as deleted without removing the row.

        Raises:
            TypeError: if the model does not support soft deletion.
        """
        if not isinstance(entity, SoftDeleteMixin):
            raise TypeError(f"{self._model.__name__} does not support soft delete")
        from datetime import datetime

        entity.deleted_at = datetime.now(timezone.utc)
        await self._session.flush()
