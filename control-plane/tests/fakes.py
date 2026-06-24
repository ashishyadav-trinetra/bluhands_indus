"""In-memory fakes for offline unit/integration tests.

These implement the repository protocols with dict/list storage so service and
HTTP-layer logic can be tested without a database or Redis.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.db.models.build_run import BuildRun
from app.db.models.credit import CreditWallet
from app.db.models.enums import BuildStatus, Industry
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.tenant import Tenant
from app.db.models.user import User


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryUserRepo:
    """In-memory UserRepositoryProtocol."""

    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, User] = {}
        self._by_email: dict[str, User] = {}

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return self._by_email.get(email.lower())

    async def add(self, user: User) -> User:
        if user.id is None:
            user.id = uuid.uuid4()
        self._by_id[user.id] = user
        self._by_email[user.email.lower()] = user
        return user


class InMemoryOrgRepo:
    """In-memory OrganizationRepositoryProtocol."""

    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Organization] = {}

    async def add(self, organization: Organization) -> Organization:
        if organization.id is None:
            organization.id = uuid.uuid4()
        self.items[organization.id] = organization
        return organization


class InMemoryMembershipRepo:
    """In-memory MembershipRepositoryProtocol."""

    def __init__(self) -> None:
        self.items: list[Membership] = []

    async def add(self, membership: Membership) -> Membership:
        if membership.id is None:
            membership.id = uuid.uuid4()
        self.items.append(membership)
        return membership

    async def list_for_user(self, user_id: uuid.UUID) -> list[Membership]:
        return [m for m in self.items if m.user_id == user_id]

    async def get_for_user_org(
        self, user_id: uuid.UUID, org_id: uuid.UUID
    ) -> Membership | None:
        for m in self.items:
            if m.user_id == user_id and m.org_id == org_id:
                return m
        return None


class InMemoryWalletRepo:
    """In-memory WalletRepositoryProtocol."""

    def __init__(self) -> None:
        self.wallets: dict[uuid.UUID, CreditWallet] = {}

    async def create_with_signup_grant(
        self, org_id: uuid.UUID, amount: int, *, idempotency_key: str
    ) -> CreditWallet:
        wallet = CreditWallet(org_id=org_id, balance=max(amount, 0), reserved=0)
        wallet.id = uuid.uuid4()
        self.wallets[org_id] = wallet
        return wallet


class InMemoryTenantRepo:
    """In-memory TenantRepositoryProtocol."""

    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, Tenant] = {}

    async def create(self, tenant: Tenant) -> Tenant:
        if tenant.id is None:
            tenant.id = uuid.uuid4()
        now = _now()
        if tenant.created_at is None:
            tenant.created_at = now
        if tenant.updated_at is None:
            tenant.updated_at = now
        self._by_id[tenant.id] = tenant
        return tenant

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        t = self._by_id.get(tenant_id)
        return t if (t is not None and not t.is_deleted) else None

    async def list_for_org(
        self, org_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> list[Tenant]:
        page = [
            t for t in self._by_id.values()
            if t.org_id == org_id and not t.is_deleted
        ]
        return page[skip : skip + limit]

    async def get_by_org_and_industry(
        self, org_id: uuid.UUID, industry: Industry
    ) -> Tenant | None:
        for t in self._by_id.values():
            if t.org_id == org_id and t.industry == industry and not t.is_deleted:
                return t
        return None


class InMemoryBuildRunRepo:
    """In-memory BuildRunRepositoryProtocol."""

    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, BuildRun] = {}

    async def create(self, build_run: BuildRun) -> BuildRun:
        if build_run.id is None:
            build_run.id = uuid.uuid4()
        now = _now()
        if build_run.created_at is None:
            build_run.created_at = now
        if build_run.updated_at is None:
            build_run.updated_at = now
        self._by_id[build_run.id] = build_run
        return build_run

    async def get_by_id(self, build_id: uuid.UUID) -> BuildRun | None:
        b = self._by_id.get(build_id)
        return b if (b is not None and not b.is_deleted) else None

    async def transition(
        self, build_run: BuildRun, *, to_status: BuildStatus, error: str | None = None
    ) -> BuildRun:
        build_run.status = to_status
        if error is not None:
            build_run.error = error
        build_run.updated_at = _now()
        return build_run

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> list[BuildRun]:
        page = [
            b for b in self._by_id.values()
            if b.tenant_id == tenant_id and not b.is_deleted
        ]
        return page[skip : skip + limit]


class FakeBuildDispatcher:
    """In-memory BuildDispatcherProtocol — records dispatched builds."""

    def __init__(self) -> None:
        self.dispatched: list[dict] = []

    def dispatch(self, build_id: uuid.UUID, *, queue: str = "default") -> str:
        task_id = f"build:{build_id}"
        self.dispatched.append({"build_id": build_id, "queue": queue, "task_id": task_id})
        return task_id


class InMemoryAudit:
    """In-memory AuditLoggerProtocol capturing events for assertions."""

    def __init__(self) -> None:
        self.events: list = []

    async def record(self, event) -> None:
        self.events.append(event)

    def actions(self) -> list[str]:
        return [e.action for e in self.events]



class FakeCreditService:
    """In-memory CreditServiceProtocol for BuildService unit tests.

    Default behaviour: all operations succeed silently.
    Set ``insufficient=True`` to simulate InsufficientCreditsError on reserve.
    """

    def __init__(self, *, insufficient: bool = False) -> None:
        self.insufficient = insufficient
        self.reserves: list[dict] = []
        self.captures: list[dict] = []
        self.refunds: list[dict] = []

    async def reserve(
        self,
        org_id: uuid.UUID,
        amount: int,
        *,
        build_run_id: uuid.UUID,
        idempotency_key: str,
    ) -> None:
        from app.core.exceptions import InsufficientCreditsError
        if self.insufficient:
            raise InsufficientCreditsError("Insufficient credits (fake)")
        self.reserves.append({"org_id": org_id, "amount": amount, "build_run_id": build_run_id})

    async def capture(
        self,
        org_id: uuid.UUID,
        *,
        build_run_id: uuid.UUID,
        idempotency_key: str,
    ) -> None:
        self.captures.append({"org_id": org_id, "build_run_id": build_run_id})

    async def refund(
        self,
        org_id: uuid.UUID,
        *,
        build_run_id: uuid.UUID,
        idempotency_key: str,
    ) -> None:
        self.refunds.append({"org_id": org_id, "build_run_id": build_run_id})


class InMemoryCreditRepo:
    """In-memory CreditRepositoryProtocol for CreditService unit tests."""

    def __init__(self) -> None:
        self._org_wallets: dict[uuid.UUID, CreditWallet] = {}
        self._txns_by_key: dict[str, object] = {}
        self._reserve_by_build: dict[uuid.UUID, object] = {}

    def seed_wallet(self, org_id: uuid.UUID, *, balance: int = 500, reserved: int = 0) -> CreditWallet:
        wallet = CreditWallet(org_id=org_id, balance=balance, reserved=reserved)
        wallet.id = uuid.uuid4()
        self._org_wallets[org_id] = wallet
        return wallet

    async def get_wallet_for_update(self, org_id: uuid.UUID) -> CreditWallet | None:
        return self._org_wallets.get(org_id)

    async def get_transaction_by_key(self, idempotency_key: str) -> object | None:
        return self._txns_by_key.get(idempotency_key)

    async def get_reserve_for_build(self, build_run_id: uuid.UUID) -> object | None:
        return self._reserve_by_build.get(build_run_id)

    async def add_transaction(self, txn) -> object:
        from app.db.models.enums import CreditTxnKind
        if txn.id is None:
            txn.id = uuid.uuid4()
        self._txns_by_key[txn.idempotency_key] = txn
        if txn.kind == CreditTxnKind.RESERVE:
            self._reserve_by_build[txn.build_run_id] = txn
        return txn


class FakeAgentClient:
    """In-memory BluHandsAgentClientProtocol.

    Default behaviour: immediate success with a stub preview URL.
    Set ``fail=True`` to simulate agent failure.
    """

    def __init__(self, *, fail: bool = False, fail_on_poll: bool = False) -> None:
        self.fail = fail
        self.fail_on_poll = fail_on_poll
        self.started: list[dict] = []
        self.polled: list[str] = []

    async def start_build(
        self,
        build_id: str,
        *,
        prompt: str,
        tenant_id: str,
        industry: str,
        llm_model: str | None = None,
        medusa_url: str | None = None,
        publishable_key: str = "",
        manifest: dict | None = None,
    ) -> str:
        if self.fail:
            raise RuntimeError("Agent service unavailable")
        self.started.append({"build_id": build_id, "prompt": prompt, "llm_model": llm_model})
        return f"stub-job-{build_id}"

    async def get_status(self, job_id: str) -> dict:
        self.polled.append(job_id)
        if self.fail_on_poll:
            return {"status": "failed", "preview_url": None, "error": "build failed"}
        return {
            "status": "success",
            "preview_url": f"https://preview.bluhands.dev/{job_id}",
            "error": None,
        }


class InMemoryPaymentRepo:
    """In-memory PaymentRepositoryProtocol for payment tests."""

    def __init__(self) -> None:
        self._by_ref: dict = {}

    async def add(self, payment):
        if payment.id is None:
            payment.id = uuid.uuid4()
        self._by_ref[payment.provider_ref] = payment
        return payment

    async def get_by_provider_ref(self, provider_ref: str):
        return self._by_ref.get(provider_ref)


class InMemoryApiKeyRepo:
    """In-memory ApiKeyRepositoryProtocol for API-key tests."""

    def __init__(self) -> None:
        self._by_id: dict = {}
        self._by_hash: dict = {}

    async def add(self, key):
        if key.id is None:
            key.id = uuid.uuid4()
        from datetime import datetime
        if getattr(key, "created_at", None) is None:
            key.created_at = datetime.now(timezone.utc)
        self._by_id[key.id] = key
        self._by_hash[key.key_hash] = key
        return key

    async def get_by_hash(self, key_hash: str):
        return self._by_hash.get(key_hash)

    async def get_by_id(self, key_id):
        return self._by_id.get(key_id)

    async def list_for_org(self, org_id):
        return [k for k in self._by_id.values() if k.org_id == org_id]
