"""add build_runs github fields + started_by

Revision ID: 0006_build_github
Revises: 0005_github_account
Create Date: 2026-06-23
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_build_github"
down_revision: str | None = "0005_github_account"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("build_runs", sa.Column("started_by", UUID, nullable=True))
    op.add_column("build_runs", sa.Column("github_repo_url", sa.String(length=500), nullable=True))
    op.add_column("build_runs", sa.Column("github_branch", sa.String(length=200), nullable=True))
    op.add_column(
        "build_runs",
        sa.Column("github_push", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "build_runs",
        sa.Column("github_pull", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("build_runs", "github_pull")
    op.drop_column("build_runs", "github_push")
    op.drop_column("build_runs", "github_branch")
    op.drop_column("build_runs", "github_repo_url")
    op.drop_column("build_runs", "started_by")
