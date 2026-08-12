"""Authentication routes: register, login, refresh, logout, and profile.

The refresh token is delivered only as an HttpOnly + Secure + SameSite=Strict
cookie (never in the response body or accessible to JS). The short-lived access
token is returned in the body for the client to send as a Bearer header.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.api.v1.dependencies.providers import get_rate_limiter
from app.api.v1.dependencies.services import get_auth_service
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, RateLimitError
from app.core.rate_limit import RateLimiter
from app.db.models.user import User
from app.db.repositories.membership_repository import MembershipRepository
from app.db.session import get_db_session
from app.schemas.auth import (
    LoginRequest,
    MembershipView,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UserView,
)
from app.schemas.common import SuccessResponse
from app.services.auth_service import AuthService, IssuedTokens

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "forge_refresh"
# Root path, not "/api/v1/auth": deployments reach this API behind a prefix
# (nginx serves it at /forge/api/v1/auth), and a path-scoped cookie is withheld
# on the prefixed request, so refresh fails with "Missing refresh token".
_REFRESH_COOKIE_PATH = "/"


def _client_ip(request: Request) -> str | None:
    """Best-effort client IP (trusts the edge's X-Forwarded-For if present)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def throttle_credentials(
    request: Request,
    limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> None:
    """Throttle credential submissions per client IP (brute-force defense).

    Keyed by IP rather than email so an attacker cannot spread guesses across
    many accounts, and cannot lock a victim out by exhausting *their* bucket.

    Raises:
        RateLimitError: 429 with a Retry-After hint.
    """
    result = await limiter.hit(
        f"auth:{_client_ip(request) or 'unknown'}",
        limit=settings.auth_rate_limit_per_ip,
        window_seconds=settings.auth_rate_limit_window_seconds,
    )
    if not result.allowed:
        raise RateLimitError(
            "Too many attempts. Please try again shortly.",
            retry_after=result.retry_after,
        )


def _set_refresh_cookie(response: Response, tokens: IssuedTokens, settings: Settings) -> None:
    """Attach the refresh token as a hardened HttpOnly cookie."""
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=tokens.refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        secure=settings.is_production,  # always True in prod (HTTPS)
        samesite="strict",
        path=_REFRESH_COOKIE_PATH,
    )


def _token_envelope(request: Request, tokens: IssuedTokens) -> SuccessResponse[TokenResponse]:
    return SuccessResponse[TokenResponse](
        data=TokenResponse(access_token=tokens.access_token, expires_in=tokens.expires_in),
        request_id=_request_id(request),
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[TokenResponse],
    dependencies=[Depends(throttle_credentials)],
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> SuccessResponse[TokenResponse]:
    """Create an account (user + org + wallet) and return an access token."""
    user = await service.register(payload, ip=_client_ip(request))
    tokens = service.issue_tokens(user)
    _set_refresh_cookie(response, tokens, settings)
    return _token_envelope(request, tokens)


@router.post(
    "/login",
    response_model=SuccessResponse[TokenResponse],
    dependencies=[Depends(throttle_credentials)],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> SuccessResponse[TokenResponse]:
    """Authenticate and issue a token pair."""
    user = await service.authenticate(payload.email, payload.password, ip=_client_ip(request))
    tokens = service.issue_tokens(user)
    _set_refresh_cookie(response, tokens, settings)
    return _token_envelope(request, tokens)


@router.post("/refresh", response_model=SuccessResponse[TokenResponse])
async def refresh(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> SuccessResponse[TokenResponse]:
    """Rotate the refresh cookie and return a new access token."""
    refresh_token = request.cookies.get(_REFRESH_COOKIE)
    if not refresh_token:
        raise AuthenticationError("Missing refresh token")
    tokens = await service.refresh(refresh_token, ip=_client_ip(request))
    _set_refresh_cookie(response, tokens, settings)
    return _token_envelope(request, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    """Revoke the current access + refresh tokens and clear the cookie."""
    await service.logout(
        access_jti=request.state.access_jti,
        access_exp=request.state.access_exp,
        refresh_token=request.cookies.get(_REFRESH_COOKIE),
        user_id=user.id,
        ip=_client_ip(request),
    )
    response.delete_cookie(_REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=SuccessResponse[MeResponse])
async def me(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[MeResponse]:
    """Return the current user's profile and organization memberships."""
    memberships = await MembershipRepository(session).list_for_user(user.id)
    membership_views = [
        MembershipView(
            org_id=m.org_id,
            organization_name=m.organization.name,
            role=m.role.value,
        )
        for m in memberships
    ]
    data = MeResponse(
        user=UserView(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_platform_admin=user.is_platform_admin,
            created_at=user.created_at,
        ),
        memberships=membership_views,
    )
    return SuccessResponse[MeResponse](data=data, request_id=_request_id(request))
