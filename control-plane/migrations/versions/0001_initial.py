"""initial control-plane schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-15
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _timestamps() -> list[sa.Column]:
    """Common created_at/updated_at columns."""
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _soft_delete() -> sa.Column:
    return sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)


def upgrade() -> None:
    # organizations
    op.create_table(
        "organizations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *_timestamps(),
        _soft_delete(),
    )
    op.create_index("ix_organizations_deleted_at", "organizations", ["deleted_at"])

    # users
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
        _soft_delete(),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_external_id", "users", ["external_id"])
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])

    # memberships
    op.create_table(
        "memberships",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        *_timestamps(),
        _soft_delete(),
        sa.UniqueConstraint("user_id", "org_id", name="user_org"),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_org_id", "memberships", ["org_id"])
    op.create_index("ix_memberships_deleted_at", "memberships", ["deleted_at"])

    # tenants
    op.create_table(
        "tenants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("org_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("industry", sa.String(20), nullable=False),
        sa.Column("isolation_level", sa.String(20), nullable=False, server_default="pooled"),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("region", sa.String(40), nullable=False, server_default="us-east-1"),
        sa.Column("display_name", sa.String(200), nullable=True),
        *_timestamps(),
        _soft_delete(),
    )
    op.create_index("ix_tenants_org_id", "tenants", ["org_id"])
    op.create_index("ix_tenants_industry", "tenants", ["industry"])
    op.create_index("ix_tenants_status", "tenants", ["status"])
    op.create_index("ix_tenants_deleted_at", "tenants", ["deleted_at"])

    # backends
    op.create_table(
        "backends",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("catalog_ref", sa.String(120), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("api_url", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        *_timestamps(),
        _soft_delete(),
    )
    op.create_index("ix_backends_tenant_id", "backends", ["tenant_id"])
    op.create_index("ix_backends_status", "backends", ["status"])
    op.create_index("ix_backends_deleted_at", "backends", ["deleted_at"])

    # build_runs
    op.create_table(
        "build_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("celery_task_id", sa.String(155), nullable=True),
        sa.Column("conversation_id", sa.String(64), nullable=True),
        sa.Column("persistence_uri", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("credits_cost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("preview_url", sa.String(500), nullable=True),
        sa.Column("prod_url", sa.String(500), nullable=True),
        sa.Column("test_report_uri", sa.String(500), nullable=True),
        sa.Column("llm_cost", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        *_timestamps(),
        _soft_delete(),
    )
    op.create_index("ix_build_runs_tenant_id", "build_runs", ["tenant_id"])
    op.create_index("ix_build_runs_celery_task_id", "build_runs", ["celery_task_id"])
    op.create_index("ix_build_runs_status", "build_runs", ["status"])
    op.create_index("ix_build_runs_deleted_at", "build_runs", ["deleted_at"])

    # credit_wallets
    op.create_table(
        "credit_wallets",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("org_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.BigInteger(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.UniqueConstraint("org_id", name="uq_credit_wallets_org_id"),
        sa.CheckConstraint("balance >= 0", name="balance_non_negative"),
        sa.CheckConstraint("reserved >= 0", name="reserved_non_negative"),
    )
    op.create_index("ix_credit_wallets_org_id", "credit_wallets", ["org_id"])

    # credit_transactions
    op.create_table(
        "credit_transactions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("wallet_id", UUID, sa.ForeignKey("credit_wallets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("build_run_id", UUID, sa.ForeignKey("build_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("idempotency_key", name="uq_credit_transactions_idempotency_key"),
    )
    op.create_index("ix_credit_transactions_wallet_id", "credit_transactions", ["wallet_id"])
    op.create_index("ix_credit_transactions_build_run_id", "credit_transactions", ["build_run_id"])
    op.create_index("ix_credit_transactions_idempotency_key", "credit_transactions", ["idempotency_key"])

    # payments
    op.create_table(
        "payments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("org_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_ref", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("credits_granted", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        *_timestamps(),
        sa.UniqueConstraint("provider_ref", name="uq_payments_provider_ref"),
    )
    op.create_index("ix_payments_org_id", "payments", ["org_id"])
    op.create_index("ix_payments_provider_ref", "payments", ["provider_ref"])
    op.create_index("ix_payments_status", "payments", ["status"])

    # api_keys
    op.create_table(
        "api_keys",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("org_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("rate_limit_per_min", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_org_id", "api_keys", ["org_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    # audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("org_id", UUID, nullable=True),
        sa.Column("tenant_id", UUID, nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target", sa.String(255), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_audit_events_actor", "audit_events", ["actor"])
    op.create_index("ix_audit_events_org_id", "audit_events", ["org_id"])
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])


def downgrade() -> None:
    for table in (
        "audit_events",
        "api_keys",
        "payments",
        "credit_transactions",
        "credit_wallets",
        "build_runs",
        "backends",
        "tenants",
        "memberships",
        "users",
        "organizations",
    ):
        op.drop_table(table)
