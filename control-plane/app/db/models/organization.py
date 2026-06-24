"""Organization model — the tenant (paying customer) boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import OrgPlan

if TYPE_CHECKING:
    from app.db.models.api_key import ApiKey
    from app.db.models.credit import CreditWallet
    from app.db.models.membership import Membership
    from app.db.models.payment import Payment
    from app.db.models.tenant import Tenant


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A customer organization; owns tenants, a credit wallet, and members."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    plan: Mapped[OrgPlan] = mapped_column(
        Enum(OrgPlan, native_enum=False, length=20),
        default=OrgPlan.FREE,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    tenants: Mapped[list[Tenant]] = relationship(back_populates="organization")
    wallet: Mapped[CreditWallet | None] = relationship(
        back_populates="organization", uselist=False
    )
    api_keys: Mapped[list[ApiKey]] = relationship(back_populates="organization")
    payments: Mapped[list[Payment]] = relationship(back_populates="organization")
