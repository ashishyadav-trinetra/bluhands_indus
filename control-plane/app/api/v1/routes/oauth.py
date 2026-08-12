"""Google Sign-In — OIDC authorization code flow with PKCE.

Two hops:

1. ``GET /auth/oauth/google/start`` — mint a one-time ``state`` + PKCE verifier,
   park them in Redis, and 302 the browser to Google.
2. ``GET /auth/oauth/google/callback`` — Google returns ``code`` + ``state``. We
   check the state is one we issued (CSRF), exchange the code for an
   ``id_token``, verify that token's signature against Google's JWKS, then
   load-or-create the user and hand back our own session.

After the callback the user holds an ordinary control-plane token pair, exactly
as if they had signed in with a password. Nothing downstream knows or cares that
Google was involved.

No new dependencies: httpx and PyJWT (with its JWKS client) are already here.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, Query, Request, Response
from redis.asyncio import Redis

from app.api.v1.dependencies.services import get_auth_service
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, AuthenticationError
from app.providers.redis_client import get_redis
from app.services.auth_service import AuthService, IssuedTokens

router = APIRouter(prefix="/auth/oauth", tags=["auth"])

_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# A sign-in attempt must complete inside this window.
_STATE_TTL_SECONDS = 600
_STATE_PREFIX = "oauth:google:state:"

# Reused across requests so Google's signing keys are fetched once, not per login.
_jwk_client = jwt.PyJWKClient(_JWKS_URL)


class OAuthNotConfiguredError(AppError):
    """Google sign-in was attempted without credentials configured (501)."""

    code = "OAUTH_NOT_CONFIGURED"
    http_status = 501


def _require_config(settings: Settings) -> None:
    if not (settings.google_client_id and settings.google_client_secret):
        raise OAuthNotConfiguredError(
            "Google sign-in is not configured on this deployment."
        )


def _pkce_pair() -> tuple[str, str]:
    """Return ``(verifier, challenge)`` for PKCE S256."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


@router.get("/google/start")
async def google_start(
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis),
) -> Response:
    """Begin Google sign-in: park the PKCE verifier and redirect to Google."""
    _require_config(settings)

    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()
    nonce = secrets.token_urlsafe(16)

    # The verifier never travels through the browser — only its hash does.
    await redis.setex(f"{_STATE_PREFIX}{state}", _STATE_TTL_SECONDS, f"{verifier}:{nonce}")

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        # Always show the account chooser rather than silently reusing a session.
        "prompt": "select_account",
    }
    return Response(
        status_code=302, headers={"Location": f"{_AUTHORIZE_URL}?{urlencode(params)}"}
    )


async def _consume_state(redis: Redis, state: str) -> tuple[str, str]:
    """Pop the stored verifier + nonce for ``state``. Single use.

    Raises:
        AuthenticationError: if the state is unknown, expired, or already used.
    """
    key = f"{_STATE_PREFIX}{state}"
    stored = await redis.get(key)
    await redis.delete(key)  # single-use: a replayed callback finds nothing
    if not stored:
        raise AuthenticationError("Sign-in request expired. Please try again.")
    value = stored.decode() if isinstance(stored, bytes) else stored
    verifier, _, nonce = value.partition(":")
    return verifier, nonce


async def _exchange_code(code: str, verifier: str, settings: Settings) -> str:
    """Trade the authorization code for Google's signed ``id_token``."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
        )
    if response.status_code != 200:
        raise AuthenticationError("Google rejected the sign-in. Please try again.")
    id_token = response.json().get("id_token")
    if not id_token:
        raise AuthenticationError("Google did not return an identity token.")
    return id_token


def _verify_id_token(id_token: str, nonce: str, settings: Settings) -> dict:
    """Verify signature, issuer, audience, expiry, and nonce. Return the claims."""
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=list(_ISSUERS),
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Could not verify the Google identity token.") from exc

    # Binds this token to the request we started — blocks token replay/injection.
    if claims.get("nonce") != nonce:
        raise AuthenticationError("Google identity token did not match this request.")
    if not claims.get("email"):
        raise AuthenticationError("Google did not share an email address.")
    # Google sets this false for unverified Workspace-adjacent addresses; treating
    # those as owned would let someone claim an account they don't control.
    if claims.get("email_verified") is False:
        raise AuthenticationError("Your Google email address is not verified.")
    return claims


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    """Complete Google sign-in and redirect into the app with a session."""
    _require_config(settings)

    if error or not code or not state:
        # User cancelled at Google's consent screen, or the request was malformed.
        return _redirect_to_frontend(settings, tokens=None, failed=True)

    verifier, nonce = await _consume_state(redis, state)
    id_token = await _exchange_code(code, verifier, settings)
    claims = _verify_id_token(id_token, nonce, settings)

    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else None

    user = await service.provision_from_oauth(
        provider="google",
        subject=claims["sub"],
        email=claims["email"],
        full_name=claims.get("name"),
        ip=ip,
    )
    if not user.is_active:
        raise AuthenticationError("This account has been deactivated.")

    return _redirect_to_frontend(settings, tokens=service.issue_tokens(user))


def _redirect_to_frontend(
    settings: Settings, *, tokens: IssuedTokens | None, failed: bool = False
) -> Response:
    """Send the browser back to the SPA, carrying the session in a cookie.

    The refresh token goes in the same HttpOnly cookie the password flow uses, so
    the SPA lands, calls ``/auth/refresh``, and is signed in. The access token is
    deliberately NOT put in the URL — query strings leak into history, logs, and
    Referer headers.
    """
    base = settings.frontend_base_url.rstrip("/")
    location = f"{base}/login?error=oauth" if failed else f"{base}/"
    response = Response(status_code=302, headers={"Location": location})

    if tokens is not None:
        response.set_cookie(
            key="forge_refresh",
            value=tokens.refresh_token,
            max_age=settings.refresh_token_ttl_seconds,
            httponly=True,
            secure=settings.is_production,
            # "lax" (not "strict") so the cookie survives Google's cross-site
            # redirect back to us — a strict cookie is withheld on that hop.
            samesite="lax",
            # Root path — see _REFRESH_COOKIE_PATH in auth.py.
            path="/",
        )
    return response
