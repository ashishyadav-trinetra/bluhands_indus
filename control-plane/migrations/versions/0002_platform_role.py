"""add users.platform_role

Revision ID: 0002_platform_role
Revises: 0001_initial
Create Date: 2026-06-23
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_platform_role"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing rows default to 'user' via server_default.
    op.add_column(
        "users",
        sa.Column(
            "platform_role",
            sa.String(length=20),
            nullable=False,
            server_default="user",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "platform_role")
