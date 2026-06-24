"""API key model — machine authentication for admins/integrations.

Only the SHA-256 hash of the key is stored. The plaintext is shown to the user
exactly once at creation and never persisted.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.organization import Organization


class ApiKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named API key bound to an organization."""

    __tablename__ = "api_keys"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # SHA-256 hex digest of the full key — never the plaintext.
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # Short non-secret prefix to help users identify a key (e.g. "fk_live_abcd").
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="api_keys")

    @property
    def is_active(self) -> bool:
        """True if the key has not been revoked."""
        return self.revoked_at is None
