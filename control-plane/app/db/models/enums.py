"""Domain enums shared across models and schemas."""

from __future__ import annotations

import enum


class Role(str, enum.Enum):
    """Membership roles within an organization (RBAC)."""

    OWNER = "owner"
    EDITOR = "editor"
    BILLING = "billing"
    VIEWER = "viewer"
    PLATFORM_ADMIN = "platform_admin"


class PlatformRole(str, enum.Enum):
    """Platform-level role (distinct from org membership ``Role``).

    Gates which LLM the agent uses for a user's builds (see
    ``Settings.model_for_role``):
    - ``USER``   : normal customer — default model.
    - ``ADMIN``  : platform admin — default model + admin panel access.
    - ``TESTER`` : restricted to a single fixed model (e.g. MiniMax).
    - ``SELF``   : internal staff — the self-hosted model (e.g. Qwen 3.6).
    """

    USER = "user"
    ADMIN = "admin"
    TESTER = "tester"
    SELF = "self"


class Industry(str, enum.Enum):
    """Supported industries (selects backend template + agent skill pack)."""

    ECOMMERCE = "ecommerce"
    CRM = "crm"
    RESTAURANT = "restaurant"
    ERP = "erp"
    HEALTHCARE = "healthcare"


class IsolationLevel(str, enum.Enum):
    """Tenant data isolation tier."""

    POOLED = "pooled"
    SCHEMA = "schema"
    SILOED = "siloed"


class TenantStatus(str, enum.Enum):
    """Lifecycle state of a tenant."""

    CREATED = "created"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class BackendStatus(str, enum.Enum):
    """Lifecycle state of a provisioned backend."""

    PENDING = "pending"
    PROVISIONING = "provisioning"
    READY = "ready"
    FAILED = "failed"


class BuildStatus(str, enum.Enum):
    """Finite-state machine for a build run."""

    QUEUED = "queued"
    PROVISIONING = "provisioning"
    BUILDING = "building"
    TESTING = "testing"
    REVIEW = "review"
    LIVE = "live"
    UPDATING = "updating"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CreditTxnKind(str, enum.Enum):
    """Credit ledger entry kind (reserve/capture/refund pattern)."""

    GRANT = "grant"
    RESERVE = "reserve"
    CAPTURE = "capture"
    REFUND = "refund"
    ADJUST = "adjust"


class PaymentStatus(str, enum.Enum):
    """Payment lifecycle (credits granted only on CONFIRMED)."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REFUNDED = "refunded"


class OrgPlan(str, enum.Enum):
    """Billing plan tier (affects quotas and isolation policy)."""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"
