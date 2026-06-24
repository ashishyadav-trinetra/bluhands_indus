"""Credit wallet and ledger models.

The wallet holds the current balance and a ``reserved`` amount. Builds follow a
reserve -> capture/refund pattern so credits are never double-spent across async
jobs. Every mutation is an append-only ledger row with an idempotency key.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import CreditTxnKind

if TYPE_CHECKING:
    from app.db.models.build_run import BuildRun
    from app.db.models.organization import Organization


class CreditWallet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One wallet per organization. Balances are non-negative integers."""

    __tablename__ = "credit_wallets"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    reserved: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="wallet")
    transactions: Mapped[list[CreditTransaction]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )


class CreditTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only ledger entry. ``idempotency_key`` prevents double application
    of the same logical operation (e.g. a retried webhook or task).
    """

    __tablename__ = "credit_transactions"

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("credit_wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    build_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("build_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[CreditTxnKind] = mapped_column(
        Enum(CreditTxnKind, native_enum=False, length=20), nullable=False
    )
    # Signed amount: positive adds available credits, negative removes.
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=False, index=True
    )

    wallet: Mapped[CreditWallet] = relationship(back_populates="transactions")
    build_run: Mapped[BuildRun | None] = relationship(back_populates="credit_transactions")
