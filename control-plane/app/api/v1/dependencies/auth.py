"""Authentication & authorization dependencies.

``get_current_user`` validates the bearer access token (signature, expiry, type,
and blocklist) and loads the user. ``require_org_role`` / ``require_platform_admin``
enforce RBAC. Authorization failures raise typed errors mapped to 401/403.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, Header, Path, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.providers import get_supabase_verifier, get_token_manager
from app.api.v1.dependencies.services import get_auth_service
from app.core.authz import is_allowed
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import RedisTokenBlocklist, TokenManager, TokenType
from app.db.models.enums import Role
from app.db.models.user import User
from app.db.repositories.membership_repository import MembershipRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import get_db_session
from app.providers.redis_client import get_redis
from app.services.auth_service import AuthService


def _extract_bearer(authorization: str | None) -> str:
    """Return the token from an ``Authorization: Bearer <token>`` header."""
    if not authorization:
        raise AuthenticationError("Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Invalid Authorization header")
    return token


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    token_manager: TokenManager = Depends(get_token_manager),
    redis: Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db_session),
    supabase_verifier=Depends(get_supabase_verifier),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Resolve and return the authenticated user from the access token.

    Accepts EITHER a control-plane RS256 token (machine/admin) OR a Supabase
    access token (platform login, ADR-13). The RS256 path is tried first; if the
    token isn't one of ours, we fall back to Supabase verification + JIT user
    provisioning. Stashes the RS256 token ``jti``/``exp`` on ``request.state`` so
    logout can revoke the exact token in use.

    Raises:
        AuthenticationError: if the token is missing, invalid, revoked, or the
            user does not exist / is inactive.
    """
    token = _extract_bearer(authorization)
    try:
        payload = token_manager.decode(token, expected_type=TokenType.ACCESS)
    except AuthenticationError:
        # Not a control-plane token — try the Supabase platform login.
        return await _resolve_supabase_user(token, request, supabase_verifier, auth_service)

    blocklist = RedisTokenBlocklist(redis)
    if await blocklist.is_blocked(payload["jti"]):
        raise AuthenticationError("Token has been revoked")

    user = await UserRepository(session).get_by_id(uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthenticationError("User is no longer active")

    request.state.access_jti = payload["jti"]
    request.state.access_exp = int(payload["exp"])
    return user


async def _resolve_supabase_user(
    token: str,
    request: Request,
    verifier,
    auth_service: AuthService,
) -> User:
    """Verify a Supabase token and load-or-provision the matching platform user."""
    if verifier is None:
        raise AuthenticationError("Invalid or expired token")
    claims = await verifier.verify(token)
    email = claims.get("email")
    if not email:
        raise AuthenticationError("Supabase token is missing an email claim")
    full_name = (claims.get("user_metadata") or {}).get("full_name")
    user = await auth_service.provision_from_supabase(
        external_id=claims.get("sub"),
        email=email,
        full_name=full_name,
    )
    if not user.is_active:
        raise AuthenticationError("User is no longer active")
    request.state.auth_via = "supabase"
    return user


def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    """Allow only platform admins (defense in depth: DB flag is authoritative)."""
    if not user.is_platform_admin:
        raise AuthorizationError("Platform admin privileges required")
    return user


def require_org_role(*allowed: Role):
    """Build a dependency that requires one of ``allowed`` roles in the org.

    The org is taken from the ``org_id`` path parameter. Platform admins always
    pass. Used by org-scoped routes (tenants/builds) in later phases.
    """
    allowed_set = frozenset(allowed)

    async def _dependency(
        org_id: uuid.UUID = Path(...),
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        if user.is_platform_admin:
            return user
        membership = await MembershipRepository(session).get_for_user_org(user.id, org_id)
        if membership is None or not is_allowed(membership.role, allowed_set):
            raise AuthorizationError("You do not have access to this organization")
        return user

    return _dependency
