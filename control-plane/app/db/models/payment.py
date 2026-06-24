"""Payment model — a credit top-up via a payment provider.

Credits are granted ONLY when ``status`` transitions to CONFIRMED via a
signature-verified webhook — never on a frontend signal.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import PaymentStatus

if TYPE_CHECKING:
    from app.db.models.organization import Organization


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A payment intent/charge mapped to a credit grant."""

    __tablename__ = "payments"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    # Provider's id (payment intent / order id). Unique to dedupe webhooks.
    provider_ref: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, length=20),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True,
    )
    credits_granted: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="payments")
