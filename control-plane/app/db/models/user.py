"""User model — a human identity (mirrors Supabase Auth in production)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import PlatformRole

if TYPE_CHECKING:
    from app.db.models.membership import Membership


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A platform user. Passwords are never stored here in production (Supabase
    owns credentials); ``password_hash`` exists only for the dev JWT fallback.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    # External IdP subject (Supabase user id). Indexed for fast lookup on login.
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # Dev-only password hash (argon2). Null when identity is delegated to Supabase.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Defense-in-depth: admin routes require this DB flag AND the admin role.
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Platform role (user/admin/tester/self) — gates the agent's LLM per user.
    platform_role: Mapped[str] = mapped_column(
        String(20),
        default=PlatformRole.USER.value,
        server_default=PlatformRole.USER.value,
        nullable=False,
    )

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
