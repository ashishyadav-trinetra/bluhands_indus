"""no-op (GitHub uses Nango — no bespoke github_accounts table)

Revision ID: 0005_github_account
Revises: 0004_tenant_domain
Create Date: 2026-06-23

Originally added a github_accounts table for a standalone GitHub OAuth. That was
superseded by the existing Nango integration, so this migration is intentionally
a no-op. Kept (not deleted) to preserve the revision chain. Safe to squash later.
"""
from __future__ import annotations

from collections.abc import Sequence

revision: str = "0005_github_account"
down_revision: str | None = "0004_tenant_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
