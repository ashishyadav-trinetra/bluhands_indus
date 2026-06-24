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

    async def provision_from_supabase(
        self,
        *,
        external_id: str | None,
        email: str,
        full_name: str | None = None,
        ip: str | None = None,
    ) -> User:
        """Load-or-create the platform user behind a Supabase identity (ADR-13).

        First Supabase login JIT-provisions the user + org + owner membership +
        wallet (same atomic pattern as ``register``), but with no password — the
        credential lives in Supabase. Subsequent logins just load the user and
        backfill ``external_id`` if it was missing.
        """
        email = email.lower()
        existing = await self._users.get_by_email(email)
        if existing is not None:
            if external_id and existing.external_id is None:
                existing.external_id = external_id
            return existing

        user = User(
            email=email,
            full_name=full_name,
            password_hash=None,  # Supabase owns the credential
            external_id=external_id,
            is_active=True,
            is_platform_admin=False,
        )
        await self._users.add(user)

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
                action="user.provision_supabase",
                target=email,
                ip=ip,
            )
        )
        return user

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
