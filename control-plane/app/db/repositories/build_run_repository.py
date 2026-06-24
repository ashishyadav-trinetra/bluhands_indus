"""BuildRunRepository — async repository for BuildRun rows."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.build_run import BuildRun
from app.db.models.enums import BuildStatus
from app.db.repositories.base import BaseRepository


class BuildRunRepository(BaseRepository[BuildRun]):
    """CRUD + FSM-aware queries for build runs."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, BuildRun)

    async def create(self, build_run: BuildRun) -> BuildRun:
        """Persist a new BuildRun and flush to obtain server defaults."""
        return await self.add(build_run)

    async def get_by_id(self, build_id: uuid.UUID) -> BuildRun | None:
        """Return a non-deleted BuildRun by primary key."""
        return await self.get(build_id)

    async def get_by_celery_task_id(self, task_id: str) -> BuildRun | None:
        """Return the BuildRun associated with a Celery task ID."""
        stmt = select(BuildRun).where(
            BuildRun.celery_task_id == task_id,
            BuildRun.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def transition(
        self, build_run: BuildRun, *, to_status: BuildStatus, error: str | None = None
    ) -> BuildRun:
        """Persist a status transition, optionally recording an error message.

        Does NOT validate FSM legality here — callers (Celery tasks) enforce
        that before calling, per the architecture plan (FSM enforced in service
        layer, not DB layer).
        """
        build_run.status = to_status
        if error is not None:
            build_run.error = error
        await self._session.flush()
        return build_run

    async def delete(self, build_run: BuildRun) -> None:
        """Soft-delete by setting ``deleted_at`` (consistent with existing filter pattern)."""
        build_run.deleted_at = datetime.now(timezone.utc)
        await self._session.flush()

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> list[BuildRun]:
        """Return non-deleted BuildRuns for a tenant, newest first."""
        stmt = (
            select(BuildRun)
            .where(BuildRun.tenant_id == tenant_id, BuildRun.deleted_at.is_(None))
            .order_by(BuildRun.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
