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

from app.api.v1.dependencies.providers import get_token_manager
from app.core.authz import is_allowed
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import RedisTokenBlocklist, TokenManager, TokenType
from app.db.models.enums import Role
from app.db.models.user import User
from app.db.repositories.membership_repository import MembershipRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import get_db_session
from app.providers.redis_client import get_redis


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
) -> User:
    """Resolve and return the authenticated user from the access token.

    Every caller — password login, Google sign-in, machine, admin — presents the
    same control-plane RS256 access token; social logins are exchanged for one at
    the OAuth callback. Stashes the token's ``jti``/``exp`` on ``request.state``
    so logout can revoke the exact token in use.

    Raises:
        AuthenticationError: if the token is missing, invalid, revoked, or the
            user does not exist / is inactive.
    """
    token = _extract_bearer(authorization)
    payload = token_manager.decode(token, expected_type=TokenType.ACCESS)

    blocklist = RedisTokenBlocklist(redis)
    if await blocklist.is_blocked(payload["jti"]):
        raise AuthenticationError("Token has been revoked")

    user = await UserRepository(session).get_by_id(uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthenticationError("User is no longer active")

    request.state.access_jti = payload["jti"]
    request.state.access_exp = int(payload["exp"])
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
