"""Credit wallet and transaction repository.

Provides SELECT FOR UPDATE wallet access and append-only transaction ledger.
All mutations are called within the caller's transaction — never auto-commit.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.credit import CreditTransaction, CreditWallet
from app.db.models.enums import CreditTxnKind


class CreditRepository:
    """Data access for wallets (with row locking) and ledger transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_wallet_for_update(self, org_id: uuid.UUID) -> CreditWallet | None:
        """Return the org's wallet with a row-level write lock (SELECT FOR UPDATE).

        Must be called inside an open transaction. Blocks concurrent writers
        until the transaction commits or rolls back.
        """
        stmt = (
            select(CreditWallet)
            .where(CreditWallet.org_id == org_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_wallet(self, org_id: uuid.UUID) -> CreditWallet | None:
        """Read the org's wallet without locking (for balance display)."""
        stmt = select(CreditWallet).where(CreditWallet.org_id == org_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_transaction_by_key(self, idempotency_key: str) -> CreditTransaction | None:
        """Look up an existing ledger entry by idempotency key."""
        stmt = select(CreditTransaction).where(
            CreditTransaction.idempotency_key == idempotency_key
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_reserve_for_build(self, build_run_id: uuid.UUID) -> CreditTransaction | None:
        """Return the RESERVE ledger entry for a build run (used by refund)."""
        stmt = select(CreditTransaction).where(
            CreditTransaction.build_run_id == build_run_id,
            CreditTransaction.kind == CreditTxnKind.RESERVE,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_transaction(self, txn: CreditTransaction) -> CreditTransaction:
        """Persist a new ledger entry and flush to obtain server defaults."""
        self._session.add(txn)
        await self._session.flush()
        return txn
