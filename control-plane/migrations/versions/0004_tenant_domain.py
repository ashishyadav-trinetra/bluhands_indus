"""add tenants.custom_domain

Revision ID: 0004_tenant_domain
Revises: 0003_build_llm_model
Create Date: 2026-06-23
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_tenant_domain"
down_revision: str | None = "0003_build_llm_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("custom_domain", sa.String(length=253), nullable=True),
    )
    op.create_index("ix_tenants_custom_domain", "tenants", ["custom_domain"])


def downgrade() -> None:
    op.drop_index("ix_tenants_custom_domain", table_name="tenants")
    op.drop_column("tenants", "custom_domain")
