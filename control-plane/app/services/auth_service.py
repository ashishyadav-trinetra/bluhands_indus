"""Authentication & registration business logic.

Single responsibility: turn auth intents (register/login/refresh/logout) into
domain mutations and tokens. Depends on repository *protocols* and security
primitives (injected), never on FastAPI or raw SQL.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import PasswordHasher, TokenManager, TokenType
from app.db.models.audit import AuditEvent
from app.db.models.enums import Role
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.auth import RegisterRequest
from app.services.protocols import (
    AuditLoggerProtocol,
    MembershipRepositoryProtocol,
    OrganizationRepositoryProtocol,
    UserRepositoryProtocol,
    WalletRepositoryProtocol,
)


@dataclass(frozen=True)
class IssuedTokens:
    """Result of issuing a token pair."""

    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    """Coordinates registration and authentication."""

    def __init__(
        self,
        *,
        users: UserRepositoryProtocol,
        organizations: OrganizationRepositoryProtocol,
        memberships: MembershipRepositoryProtocol,
        wallets: WalletRepositoryProtocol,
        audit: AuditLoggerProtocol,
        password_hasher: PasswordHasher,
        token_manager: TokenManager,
        blocklist,  # TokenBlocklist (Protocol) — injected
        free_credits_on_signup: int,
        access_ttl_seconds: int,
        selfhosted_domains: str = "",
    ) -> None:
        self._users = users
        self._orgs = organizations
        self._memberships = memberships
        self._wallets = wallets
        self._audit = audit
        self._passwords = password_hasher
        self._tokens = token_manager
        self._blocklist = blocklist
        self._free_credits = free_credits_on_signup
        self._access_ttl = access_ttl_seconds
        self._selfhosted_domains = selfhosted_domains

    def _resolve_platform_role(self, email: str) -> str:
        from app.db.models.enums import PlatformRole

        if not self._selfhosted_domains:
            return PlatformRole.USER.value
        domain = email.split("@")[-1].strip().lower()
        allowed = {d.strip().lower() for d in self._selfhosted_domains.split(",") if d.strip()}
        if domain in allowed:
            return PlatformRole.SELF.value
        return PlatformRole.USER.value

    # --- Registration ------------------------------------------------------

    async def register(self, data: RegisterRequest, *, ip: str | None = None) -> User:
        """Create a user, their organization, owner membership, and wallet.

        All writes share the caller's transaction, so the account is created
        atomically (commit happens at request end).

        Raises:
            ConflictError: if the email is already registered.
        """
        email = data.email.lower()
        if await self._users.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists")

        user = User(
            email=email,
            full_name=data.full_name,
            password_hash=self._passwords.hash(data.password),
            is_active=True,
            is_platform_admin=False,
            platform_role=self._resolve_platform_role(email),
        )
        await self._users.add(user)

        organization = Organization(name=data.organization_name)
        await self._orgs.add(organization)

        membership = Membership(user_id=user.id, org_id=organization.id, role=Role.OWNER)
        await self._memberships.add(membership)

        await self._wallets.create_with_signup_grant(
            organization.id,
            self._free_credits,
            idempotency_key=f"signup:{organization.id}",
        )

        await self._audit.record(
            AuditEvent(
                actor=f"user:{user.id}",
                org_id=organization.id,
                action="user.register",
                target=email,
                ip=ip,
            )
        )
        return user

    async def provision_from_oauth(
        self,
        *,
        provider: str,
        subject: str,
        email: str,
        full_name: str | None = None,
        ip: str | None = None,
    ) -> User:
        """Load-or-create the platform user behind a federated identity.

        First social login JIT-provisions the user + org + owner membership +
        wallet (same atomic pattern as ``register``), but with no password — the
        identity provider owns the credential. Subsequent logins just load the
        user and backfill ``external_id`` if it was missing.

        ``external_id`` is namespaced (``google:1234``) so two providers issuing
        the same opaque subject can never collide into one account.

        Args:
            provider: Identity provider key, e.g. ``"google"``.
            subject: The provider's stable, opaque user id (never the email).
        """
        email = email.lower()
        external_id = f"{provider}:{subject}"

        existing = await self._users.get_by_email(email)
        if existing is not None:
            if existing.external_id is None:
                existing.external_id = external_id
            # Self-heal: ensure the user has an org + owner membership. Users
            # created before provisioning existed (or by a half-completed first
            # login) can have none — which leaves them with no org, so they can't
            # reach settings or create a tenant. Back-fill on next login.
            memberships = await self._memberships.list_for_user(existing.id)
            if not memberships:
                await self._provision_org(
                    existing, email=email, full_name=full_name, ip=ip,
                    action=f"user.provision_{provider}_backfill",
                )
            return existing

        user = User(
            email=email,
            full_name=full_name,
            password_hash=None,  # the identity provider owns the credential
            external_id=external_id,
            is_active=True,
            is_platform_admin=False,
            platform_role=self._resolve_platform_role(email),
        )
        await self._users.add(user)
        await self._provision_org(
            user, email=email, full_name=full_name, ip=ip,
            action=f"user.provision_{provider}",
        )
        return user

    async def _provision_org(
        self,
        user: User,
        *,
        email: str,
        full_name: str | None,
        ip: str | None,
        action: str,
    ) -> None:
        """Create an organization + owner membership + signup-grant wallet for a user."""
        organization = Organization(name=full_name or email.split("@", 1)[0])
        await self._orgs.add(organization)

        membership = Membership(user_id=user.id, org_id=organization.id, role=Role.OWNER)
        await self._memberships.add(membership)

        await self._wallets.create_with_signup_grant(
            organization.id,
            self._free_credits,
            idempotency_key=f"signup:{organization.id}",
        )

        await self._audit.record(
            AuditEvent(
                actor=f"user:{user.id}",
                org_id=organization.id,
                action=action,
                target=email,
                ip=ip,
            )
        )

    # --- Login -------------------------------------------------------------

    async def authenticate(
        self, email: str, password: str, *, ip: str | None = None
    ) -> User:
        """Verify credentials and return the user.

        Uses a constant error message and always runs a hash verification to
        reduce user-enumeration and timing side-channels.

        Raises:
            AuthenticationError: on any credential failure.
        """
        user = await self._users.get_by_email(email.lower())
        password_hash = user.password_hash if user else None
        # Always verify against a hash (dummy if user missing) to equalize timing.
        valid = self._passwords.verify(password, password_hash) if password_hash else False

        if user is None or not user.is_active or not valid:
            await self._audit.record(
                AuditEvent(
                    actor=f"user:{user.id}" if user else "anonymous",
                    org_id=None,
                    action="user.login_failed",
                    target=email.lower(),
                    ip=ip,
                )
            )
            raise AuthenticationError("Invalid email or password")

        # Transparent hash upgrade: hashes made with outdated Argon2 parameters are
        # re-hashed with current settings now that we hold the plaintext. Lets us
        # raise the cost factor later without locking anyone out. Shares the
        # caller's transaction.
        if password_hash and self._passwords.needs_rehash(password_hash):
            user.password_hash = self._passwords.hash(password)

        await self._audit.record(
            AuditEvent(
                actor=f"user:{user.id}",
                action="user.login",
                target=email.lower(),
                ip=ip,
            )
        )
        return user

    # --- Tokens ------------------------------------------------------------

    def issue_tokens(self, user: User) -> IssuedTokens:
        """Mint a fresh access + refresh token pair for ``user``."""
        claims = {"is_platform_admin": user.is_platform_admin}
        access, _ = self._tokens.create_access_token(str(user.id), claims=claims)
        refresh, _ = self._tokens.create_refresh_token(str(user.id))
        return IssuedTokens(access_token=access, refresh_token=refresh, expires_in=self._access_ttl)

    async def refresh(self, refresh_token: str, *, ip: str | None = None) -> IssuedTokens:
        """Rotate a refresh token: validate, revoke the old one, issue a new pair.

        Reusing an already-rotated refresh token is rejected (replay defense).

        Raises:
            AuthenticationError: if the token is invalid, expired, reused, or
                the user no longer exists / is inactive.
        """
        payload = self._tokens.decode(refresh_token, expected_type=TokenType.REFRESH)
        jti = payload["jti"]
        if await self._blocklist.is_blocked(jti):
            raise AuthenticationError("Refresh token has been revoked")

        user = await self._users.get_by_id(uuid.UUID(payload["sub"]))
        if user is None or not user.is_active:
            raise AuthenticationError("User is no longer active")

        # Rotation: revoke the presented refresh token for its remaining life.
        remaining = max(int(payload["exp"]) - int(time.time()), 1)
        await self._blocklist.block(jti, ttl_seconds=remaining)

        await self._audit.record(
            AuditEvent(actor=f"user:{user.id}", action="user.token_refresh", ip=ip)
        )
        return self.issue_tokens(user)

    async def logout(
        self,
        *,
        access_jti: str,
        access_exp: int,
        refresh_token: str | None,
        user_id: uuid.UUID,
        ip: str | None = None,
    ) -> None:
        """Revoke the current access token and, if present, the refresh token."""
        now = int(time.time())
        await self._blocklist.block(access_jti, ttl_seconds=max(access_exp - now, 1))

        if refresh_token:
            try:
                payload = self._tokens.decode(refresh_token, expected_type=TokenType.REFRESH)
            except AuthenticationError:
                payload = None
            if payload is not None:
                ttl = max(int(payload["exp"]) - now, 1)
                await self._blocklist.block(payload["jti"], ttl_seconds=ttl)

        await self._audit.record(
            AuditEvent(actor=f"user:{user_id}", action="user.logout", ip=ip)
        )
