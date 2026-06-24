"""Audit repository (append-only)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditEvent


class AuditRepository:
    """Append-only writer for audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: AuditEvent) -> None:
        """Persist an audit event."""
        self._session.add(event)
        await self._session.flush()
