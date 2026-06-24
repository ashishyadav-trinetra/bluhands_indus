"""Task-scoped database session context manager.

Celery tasks are not request-scoped, so they cannot use the FastAPI
``get_db_session`` dependency. This module provides an equivalent async
context manager backed by the same engine/pool as the API.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker


@asynccontextmanager
async def task_session() -> AsyncIterator[AsyncSession]:
    """Yield a commit-on-success / rollback-on-error async session for tasks."""
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
