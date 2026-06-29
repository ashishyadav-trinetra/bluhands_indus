"""Repository and client protocols (Dependency Inversion).

Services depend on these abstractions, not concrete implementations, so they
can be unit-tested with in-memory fakes and backends can change without
touching business logic.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Protocol

from app.db.models.audit import AuditEvent
from app.db.models.build_run import BuildRun

if TYPE_CHECKING:
    from app.db.models.api_key import ApiKey
    from app.db.models.payment import Payment
from app.db.models.credit import CreditWallet
from app.db.models.enums import BuildStatus, Industry
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.tenant import Tenant
from app.db.models.user import User


class UserRepositoryProtocol(Protocol):
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def add(self, user: User) -> User: ...


class OrganizationRepositoryProtocol(Protocol):
    async def add(self, organization: Organization) -> Organization: ...


class MembershipRepositoryProtocol(Protocol):
    async def add(self, membership: Membership) -> Membership: ...
    async def list_for_user(self, user_id: uuid.UUID) -> list[Membership]: ...


class WalletRepositoryProtocol(Protocol):
    async def create_with_signup_grant(
        self, org_id: uuid.UUID, amount: int, *, idempotency_key: str
    ) -> CreditWallet: ...


class TenantRepositoryProtocol(Protocol):
    async def create(self, tenant: Tenant) -> Tenant: ...
    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None: ...
    async def list_for_org(self, org_id: uuid.UUID, *, skip: int, limit: int) -> list[Tenant]: ...
    async def get_by_org_and_industry(self, org_id: uuid.UUID, industry: Industry) -> Tenant | None: ...


class BuildRunRepositoryProtocol(Protocol):
    async def create(self, build_run: BuildRun) -> BuildRun: ...
    async def get_by_id(self, build_id: uuid.UUID) -> BuildRun | None: ...
    async def transition(
        self, build_run: BuildRun, *, to_status: BuildStatus, error: str | None = None
    ) -> BuildRun: ...
    async def list_for_tenant(
        self, tenant_id: uuid.UUID, *, skip: int, limit: int
    ) -> list[BuildRun]: ...
    async def delete(self, build_run: BuildRun) -> None: ...


class BuildDispatcherProtocol(Protocol):
    """Enqueue a build task on the Celery broker."""
    def dispatch(self, build_id: uuid.UUID, *, queue: str = "default") -> str: ...


class BluHandsAgentClientProtocol(Protocol):
    """Interface for the OpenHands agent service."""

    async def start_build(
        self,
        build_id: str,
        *,
        prompt: str,
        tenant_id: str,
        industry: str,
        llm_model: str | None = None,
        backend_url: str | None = None,
        publishable_key: str = "",
        manifest: dict | None = None,
        github: dict | None = None,
    ) -> str:
        """Submit a build job; returns an opaque job_id."""
        ...

    async def get_status(self, job_id: str) -> dict:
        """Poll job status. Returns dict with keys: status, preview_url, error."""
        ...


# ── Shared secondary protocols (payment, api-key, admin) ────────────────────
# These live here so services don't duplicate them locally.

class AuditLoggerProtocol(Protocol):
    """Append an audit event to the audit trail."""
    async def record(self, event: AuditEvent) -> None: ...


class PaymentRepositoryProtocol(Protocol):
    """Persistence for Payment records."""
    async def add(self, payment: "Payment") -> "Payment": ...
    async def get_by_provider_ref(self, provider_ref: str) -> "Payment | None": ...


class CreditGranterProtocol(Protocol):
    """Grant credits to an organisation."""
    async def grant(
        self, org_id: uuid.UUID, amount: int, *, reason: str, idempotency_key: str
    ) -> None: ...


class ApiKeyRepositoryProtocol(Protocol):
    """Persistence for ApiKey records."""
    async def add(self, key: "ApiKey") -> "ApiKey": ...
    async def get_by_hash(self, key_hash: str) -> "ApiKey | None": ...
    async def get_by_id(self, key_id: uuid.UUID) -> "ApiKey | None": ...
    async def list_for_org(self, org_id: uuid.UUID) -> "list[ApiKey]": ...


class CreditServiceProtocol(Protocol):
    """Credit ledger operations for build lifecycle."""

    async def reserve(
        self,
        org_id: uuid.UUID,
        amount: int,
        *,
        build_run_id: uuid.UUID,
        idempotency_key: str,
    ) -> None: ...

    async def capture(
        self,
        org_id: uuid.UUID,
        *,
        build_run_id: uuid.UUID,
        idempotency_key: str,
    ) -> None: ...

    async def refund(
        self,
        org_id: uuid.UUID,
        *,
        build_run_id: uuid.UUID,
        idempotency_key: str,
    ) -> None: ...
