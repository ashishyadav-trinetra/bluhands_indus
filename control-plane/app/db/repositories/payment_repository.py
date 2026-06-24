"""Payment repository — create + lookup by provider reference (webhook dedupe)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.payment import Payment


class PaymentRepository:
    """Data access for ``Payment`` rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, payment: Payment) -> Payment:
        """Persist a new payment and flush to obtain server defaults."""
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def get_by_provider_ref(self, provider_ref: str) -> Payment | None:
        """Look up a payment by the provider's reference id (unique)."""
        stmt = select(Payment).where(Payment.provider_ref == provider_ref)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
