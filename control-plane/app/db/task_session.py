"""Task-scoped database session context manager.

Celery tasks are not request-scoped, so they cannot use the FastAPI
``get_db_session`` dependency. This module provides an equivalent async
context manager that creates a fresh engine per invocation.

We intentionally avoid the process-wide pooled engine here. Celery prefork
workers run each retry via a new asyncio.run(), which creates a new event
loop. asyncpg connections are loop-bound, so reusing pool connections across
asyncio.run() calls raises "Future attached to a different loop". NullPool
bypasses this entirely: each session opens and closes its own connection.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@asynccontextmanager
async def task_session() -> AsyncIterator[AsyncSession]:
    """Yield a commit-on-success / rollback-on-error async session for tasks."""
    from app.core.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()
