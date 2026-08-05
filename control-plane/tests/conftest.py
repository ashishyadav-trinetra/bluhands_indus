"""Shared pytest fixtures (self-contained, no external services)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Settings, get_settings
from app.core.security import TokenManager


@pytest.fixture(scope="session")
def rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture
def settings(rsa_keypair: tuple[str, str]) -> Settings:
    private_pem, public_pem = rsa_keypair
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        env="development",
        jwt_private_key=private_pem,
        jwt_public_key=public_pem,
        jwt_issuer="forge-test",
        jwt_audience="forge-test-clients",
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=1209600,
        s3_endpoint_url=None,
        prometheus_enabled=False,
        cors_origins_csv="http://localhost:3000",
    )


@pytest.fixture
def token_manager(settings: Settings) -> TokenManager:
    return TokenManager(
        private_key=settings.resolve_jwt_private_key(),
        public_key=settings.resolve_jwt_public_key(),
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        access_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_ttl_seconds=settings.refresh_token_ttl_seconds,
    )


class _FakeScalars:
    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return self._items


class FakeResult:
    def __init__(self, items: list | None = None) -> None:
        self._items = items or []

    def scalar(self) -> int:
        return 1

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._items)


class FakeSession:
    def __init__(self, *, fail: bool = False, items: list | None = None) -> None:
        self._fail = fail
        self._items = items or []

    async def execute(self, _statement: object) -> FakeResult:
        if self._fail:
            raise RuntimeError("db down")
        return FakeResult(self._items)

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def ping(self) -> bool:
        if self._fail:
            raise RuntimeError("redis down")
        return True


@pytest.fixture
def app_factory(settings: Settings):
    from app.db.session import get_db_session
    from app.main import create_app
    from app.providers.redis_client import get_redis

    def _build(*, db_fail: bool = False, redis_fail: bool = False):
        application = create_app(settings)

        async def _override_db() -> AsyncIterator[FakeSession]:
            yield FakeSession(fail=db_fail)

        def _override_redis() -> FakeRedis:
            return FakeRedis(fail=redis_fail)

        application.dependency_overrides[get_db_session] = _override_db
        application.dependency_overrides[get_redis] = _override_redis
        application.dependency_overrides[get_settings] = lambda: settings
        return application

    return _build


@pytest.fixture
def auth_components(token_manager: TokenManager, settings: Settings):
    from app.core.security import InMemoryTokenBlocklist, PasswordHasher
    from app.services.auth_service import AuthService
    from tests.fakes import (
        InMemoryAudit,
        InMemoryMembershipRepo,
        InMemoryOrgRepo,
        InMemoryUserRepo,
        InMemoryWalletRepo,
    )

    users = InMemoryUserRepo()
    orgs = InMemoryOrgRepo()
    memberships = InMemoryMembershipRepo()
    wallets = InMemoryWalletRepo()
    audit = InMemoryAudit()
    blocklist = InMemoryTokenBlocklist()
    service = AuthService(
        users=users,
        organizations=orgs,
        memberships=memberships,
        wallets=wallets,
        audit=audit,
        password_hasher=PasswordHasher(),
        token_manager=token_manager,
        blocklist=blocklist,
        free_credits_on_signup=settings.free_credits_on_signup,
        access_ttl_seconds=settings.access_token_ttl_seconds,
        selfhosted_domains=settings.selfhosted_domains,
    )
    return {
        "service": service,
        "users": users,
        "orgs": orgs,
        "memberships": memberships,
        "wallets": wallets,
        "audit": audit,
        "blocklist": blocklist,
    }


@pytest.fixture
def auth_app(settings: Settings, auth_components):
    from app.api.v1.dependencies.services import get_auth_service
    from app.main import create_app

    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_auth_service] = lambda: auth_components["service"]
    return app
