"""add build_runs.llm_model

Revision ID: 0003_build_llm_model
Revises: 0002_platform_role
Create Date: 2026-06-23
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_build_llm_model"
down_revision: str | None = "0002_platform_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "build_runs",
        sa.Column("llm_model", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("build_runs", "llm_model")
