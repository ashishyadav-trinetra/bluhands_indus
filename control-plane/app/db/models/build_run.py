"""BuildRun model — one OpenHands build/edit job for a tenant."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import BuildStatus

if TYPE_CHECKING:
    from app.db.models.credit import CreditTransaction
    from app.db.models.tenant import Tenant


class BuildRun(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Tracks a single build job dispatched to a sandboxed OpenHands agent.

    Durable artifacts (repo, conversation state, screenshots) live in object
    storage; this row holds references and status only.
    """

    __tablename__ = "build_runs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(155), nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    persistence_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[BuildStatus] = mapped_column(
        Enum(BuildStatus, native_enum=False, length=20),
        default=BuildStatus.QUEUED,
        nullable=False,
        index=True,
    )
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    # LLM model for this build, chosen from the requester's platform role (gating).
    llm_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    credits_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    preview_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prod_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    test_report_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    llm_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="build_runs")
    credit_transactions: Mapped[list[CreditTransaction]] = relationship(
        back_populates="build_run"
    )
