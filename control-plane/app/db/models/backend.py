"""Backend model — a provisioned per-industry backend for a tenant."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import BackendStatus

if TYPE_CHECKING:
    from app.db.models.tenant import Tenant


class Backend(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Reference to a tenant's provisioned backend (Medusa, Twenty, etc.).

    Stores only references and status — never credentials (those live in the
    secrets manager; see ``secrets_refs`` design).
    """

    __tablename__ = "backends"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # e.g. "ecommerce/medusa@1.4.2" — points into the catalog.
    catalog_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    api_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[BackendStatus] = mapped_column(
        Enum(BackendStatus, native_enum=False, length=20),
        default=BackendStatus.PENDING,
        nullable=False,
        index=True,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="backends")
