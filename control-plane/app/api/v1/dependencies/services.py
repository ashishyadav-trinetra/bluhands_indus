"""Service-construction dependencies (wire repositories into services)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends

if TYPE_CHECKING:
    from app.services.admin_service import AdminService
    from app.services.api_key_service import ApiKeyService
    from app.services.payment_service import PaymentService
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.providers import (
    get_blocklist,
    get_password_hasher,
    get_token_manager,
)
from app.core.config import Settings, get_settings
from app.core.security import PasswordHasher, TokenBlocklist, TokenManager
from app.db.repositories.audit_repository import AuditRepository
from app.db.repositories.build_run_repository import BuildRunRepository
from app.db.repositories.credit_repository import CreditRepository
from app.db.repositories.membership_repository import MembershipRepository
from app.db.repositories.organization_repository import OrganizationRepository
from app.db.repositories.tenant_repository import TenantRepository
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.wallet_repository import WalletRepository
from app.db.session import get_db_session
from app.services.auth_service import AuthService
from app.services.build_service import BuildService
from app.services.credit_service import CreditService
from app.services.tenant_service import TenantService


def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
    token_manager: TokenManager = Depends(get_token_manager),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
    blocklist: TokenBlocklist = Depends(get_blocklist),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    """Construct an ``AuthService`` with request-scoped repositories."""
    return AuthService(
        users=UserRepository(session),
        organizations=OrganizationRepository(session),
        memberships=MembershipRepository(session),
        wallets=WalletRepository(session),
        audit=AuditRepository(session),
        password_hasher=password_hasher,
        token_manager=token_manager,
        blocklist=blocklist,
        free_credits_on_signup=settings.free_credits_on_signup,
        access_ttl_seconds=settings.access_token_ttl_seconds,
    )


def get_admin_service(session: AsyncSession = Depends(get_db_session)) -> "AdminService":
    """Construct an ``AdminService`` (user + org management for the admin panel)."""
    from app.services.admin_service import AdminService

    return AdminService(
        users=UserRepository(session),
        audit=AuditRepository(session),
        orgs=OrganizationRepository(session),
    )


def get_github_service(settings: Settings = Depends(get_settings)):
    """Construct a ``GithubService`` (GitHub via Nango)."""
    from app.services.github_service import GithubService

    return GithubService(settings=settings)


def get_tenant_service(
    session: AsyncSession = Depends(get_db_session),
) -> TenantService:
    """Construct a ``TenantService`` with request-scoped repositories."""
    return TenantService(
        tenants=TenantRepository(session),
        audit=AuditRepository(session),
    )


def get_build_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> BuildService:
    """Construct a ``BuildService`` with request-scoped repositories and Celery dispatcher."""
    from app.services.celery_dispatcher import CeleryBuildDispatcher

    return BuildService(
        builds=BuildRunRepository(session),
        tenants=TenantRepository(session),
        dispatcher=CeleryBuildDispatcher(),
        credits=CreditService(credits=CreditRepository(session)),
        audit=AuditRepository(session),
        build_credit_cost=settings.build_credit_cost,
    )


def get_payment_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> "PaymentService":
    """Construct a ``PaymentService`` with request-scoped repositories."""
    from app.db.repositories.payment_repository import PaymentRepository
    from app.providers.payments import PaymentFactory
    from app.services.credit_service import CreditService
    from app.services.payment_service import PaymentService

    return PaymentService(
        payments=PaymentRepository(session),
        credits=CreditService(credits=CreditRepository(session)),
        factory=PaymentFactory(settings),
        audit=AuditRepository(session),
        settings=settings,
    )


def get_domain_service(settings: Settings = Depends(get_settings)):
    """Construct a ``DomainService`` with entri credentials from settings."""
    from app.services.domain_service import DomainService

    return DomainService(
        entri_api_key=settings.entri_api_key,
        entri_app_id=settings.entri_app_id,
        entri_api_url=settings.entri_api_url,
        platform_a_record=settings.platform_a_record,
        platform_cname=settings.platform_cname,
    )


def get_credit_repository(session: AsyncSession = Depends(get_db_session)) -> CreditRepository:
    """Expose the credit repository for read-only balance endpoints."""
    return CreditRepository(session)


def get_api_key_service(session: AsyncSession = Depends(get_db_session)) -> "ApiKeyService":
    """Construct an ``ApiKeyService`` with request-scoped repositories."""
    from app.db.repositories.api_key_repository import ApiKeyRepository
    from app.services.api_key_service import ApiKeyService

    return ApiKeyService(keys=ApiKeyRepository(session), audit=AuditRepository(session))
