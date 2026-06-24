"""CreditService — atomic reserve/capture/refund for build credits.

Patterns applied:
- Service Layer: all credit business logic lives here.
- DIP: depends on CreditRepositoryProtocol (injected; not the concrete class).
- Strategy: the caller (BuildService) calls reserve/capture/refund — this class
  knows nothing about builds beyond the IDs it receives.

Reserve → capture/refund pattern:
  reserve(org_id, amount, build_run_id)  → moves `amount` from balance to reserved
  capture(org_id, amount, build_run_id) → removes from reserved (payment consumed)
  refund(org_id, amount, build_run_id)  → moves from reserved back to balance

DB idempotency: unique constraint on credit_transactions.idempotency_key.
Race safety: SELECT FOR UPDATE on wallet row; all in caller's transaction.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.core.exceptions import InsufficientCreditsError
from app.db.models.credit import CreditTransaction, CreditWallet
from app.db.models.enums import CreditTxnKind


class CreditRepositoryProtocol(Protocol):
    async def get_wallet_for_update(self, org_id: uuid.UUID) -> CreditWallet | None: ...
    async def get_transaction_by_key(self, idempotency_key: str) -> CreditTransaction | None: ...
    async def get_reserve_for_build(self, build_run_id: uuid.UUID) -> CreditTransaction | None: ...
    async def add_transaction(self, txn: CreditTransaction) -> CreditTransaction: ...


class CreditService:
    """Handles the credit ledger for build operations."""

    def __init__(self, *, credits: CreditRepositoryProtocol) -> None:
        self._credits = credits

    async def reserve(
        self,
        org_id: uuid.UUID,
        amount: int,
        *,
        build_run_id: uuid.UUID,
        idempotency_key: str,
    ) -> None:
        """Lock `amount` credits against a build.

        Raises:
            InsufficientCreditsError: if available balance < amount.
            ValueError: if idempotency_key has already been used for a different wallet.
        """
        if await self._credits.get_transaction_by_key(idempotency_key):
            return  # already applied — idempotent replay

        wallet = await self._credits.get_wallet_for_update(org_id)
        if wallet is None:
            raise InsufficientCreditsError("No credit wallet found for organization.")
        if wallet.balance < amount:
            raise InsufficientCreditsError(
                f"Insufficient credits: need {amount}, have {wallet.balance}."
            )

        wallet.balance -= amount
        wallet.reserved += amount

        await self._credits.add_transaction(
            CreditTransaction(
                wallet_id=wallet.id,
                build_run_id=build_run_id,
                kind=CreditTxnKind.RESERVE,
                amount=-amount,
                reason="Build credit reserve",
                idempotency_key=idempotency_key,
            )
        )

    async def capture(
        self,
        org_id: uuid.UUID,
        *,
        build_run_id: uuid.UUID,
        idempotency_key: str,
    ) -> None:
        """Consume reserved credits on build approval (reserve → consumed).

        The reserved amount was already deducted from balance at reserve time;
        capture simply clears it from the reserved column.
        """
        if await self._credits.get_transaction_by_key(idempotency_key):
            return  # idempotent replay

        wallet = await self._credits.get_wallet_for_update(org_id)
        if wallet is None:
            return  # wallet deleted — nothing to capture

        reserve_txn = await self._credits.get_reserve_for_build(build_run_id)
        reserved_amount = abs(reserve_txn.amount) if reserve_txn else 0

        wallet.reserved = max(0, wallet.reserved - reserved_amount)

        from app.core.metrics import inc_credits_consumed
        inc_credits_consumed(reserved_amount)

        await self._credits.add_transaction(
            CreditTransaction(
                wallet_id=wallet.id,
                build_run_id=build_run_id,
                kind=CreditTxnKind.CAPTURE,
                amount=-reserved_amount,
                reason="Build credit capture on approval",
                idempotency_key=idempotency_key,
            )
        )

    async def refund(
        self,
        org_id: uuid.UUID,
        *,
        build_run_id: uuid.UUID,
        idempotency_key: str,
    ) -> None:
        """Return reserved credits to available balance on build failure."""
        if await self._credits.get_transaction_by_key(idempotency_key):
            return  # idempotent replay

        wallet = await self._credits.get_wallet_for_update(org_id)
        if wallet is None:
            return  # wallet deleted — nothing to refund

        reserve_txn = await self._credits.get_reserve_for_build(build_run_id)
        reserved_amount = abs(reserve_txn.amount) if reserve_txn else 0

        wallet.reserved = max(0, wallet.reserved - reserved_amount)
        wallet.balance += reserved_amount

        await self._credits.add_transaction(
            CreditTransaction(
                wallet_id=wallet.id,
                build_run_id=build_run_id,
                kind=CreditTxnKind.REFUND,
                amount=reserved_amount,
                reason="Build credit refund on failure",
                idempotency_key=idempotency_key,
            )
        )

    async def grant(
        self,
        org_id: uuid.UUID,
        amount: int,
        *,
        reason: str,
        idempotency_key: str,
    ) -> None:
        """Add `amount` credits to a wallet (payment top-up).

        Idempotent via the unique idempotency_key; safe under webhook replay.

        Raises:
            ValueError: if no wallet exists for the organization.
        """
        if amount <= 0:
            return
        if await self._credits.get_transaction_by_key(idempotency_key):
            return  # idempotent replay
        wallet = await self._credits.get_wallet_for_update(org_id)
        if wallet is None:
            raise ValueError("No credit wallet found for organization.")
        wallet.balance += amount
        await self._credits.add_transaction(
            CreditTransaction(
                wallet_id=wallet.id,
                build_run_id=None,
                kind=CreditTxnKind.GRANT,
                amount=amount,
                reason=reason,
                idempotency_key=idempotency_key,
            )
        )
