"""Tenant model — one deployed app/backend instance for an organization."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import Industry, IsolationLevel, TenantStatus

if TYPE_CHECKING:
    from app.db.models.backend import Backend
    from app.db.models.build_run import BuildRun
    from app.db.models.organization import Organization


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A tenant ties an organization to an industry, a backend, and builds."""

    __tablename__ = "tenants"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    industry: Mapped[Industry] = mapped_column(
        Enum(Industry, native_enum=False, length=20), nullable=False, index=True
    )
    isolation_level: Mapped[IsolationLevel] = mapped_column(
        Enum(IsolationLevel, native_enum=False, length=20),
        default=IsolationLevel.POOLED,
        nullable=False,
    )
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, native_enum=False, length=20),
        default=TenantStatus.CREATED,
        nullable=False,
        index=True,
    )
    region: Mapped[str] = mapped_column(String(40), default="us-east-1", nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    custom_domain: Mapped[str | None] = mapped_column(String(253), nullable=True, index=True)

    organization: Mapped[Organization] = relationship(back_populates="tenants")
    backends: Mapped[list[Backend]] = relationship(back_populates="tenant")
    build_runs: Mapped[list[BuildRun]] = relationship(back_populates="tenant")
