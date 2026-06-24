"""Credit wallet repository.

Phase 2 needs only wallet creation + the initial signup grant. Atomic
deduction/refund (with row locking) arrives in the Phase 4 credit service.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.credit import CreditTransaction, CreditWallet
from app.db.models.enums import CreditTxnKind


class WalletRepository:
    """Data access for credit wallets and ledger entries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_with_signup_grant(
        self, org_id: uuid.UUID, amount: int, *, idempotency_key: str
    ) -> CreditWallet:
        """Create a wallet seeded with ``amount`` credits and a GRANT ledger row.

        Runs inside the caller's transaction so it commits atomically with the
        rest of registration.
        """
        wallet = CreditWallet(org_id=org_id, balance=max(amount, 0), reserved=0)
        self._session.add(wallet)
        await self._session.flush()

        if amount > 0:
            grant = CreditTransaction(
                wallet_id=wallet.id,
                kind=CreditTxnKind.GRANT,
                amount=amount,
                reason="signup_bonus",
                idempotency_key=idempotency_key,
            )
            self._session.add(grant)
            await self._session.flush()
        return wallet
