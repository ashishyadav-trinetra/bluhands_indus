"""Supabase JWT verification — platform-user identity (ADR-13).

Supabase is the platform login. The control-plane verifies the Supabase-issued
access token on incoming requests, *additive* to its own RS256 machine/admin auth
(``get_current_user`` tries the RS256 token first, then falls back to here).

Two verification modes, picked from config:
- **HS256** with the project's JWT secret (``supabase_jwt_secret``) — offline-
  verifiable, no network. Fastest option for development.
- **Asymmetric** (RS256/ES256) via the project's JWKS URL (``supabase_jwks_url``);
  keys are fetched once and cached by PyJWT's ``PyJWKClient``.

The public ``verify()`` method is *async* to avoid blocking the event loop: the
JWKS path does a synchronous HTTP fetch internally (PyJWT limitation), so it is
off-loaded to a thread pool via ``asyncio.to_thread()``. HS256 is effectively
free (no I/O) but is still run through the same interface for consistency.
"""

from __future__ import annotations

import asyncio
from typing import Any

import jwt

from app.core.exceptions import AuthenticationError


class SupabaseVerifier:
    """Verifies Supabase access tokens and returns their claims."""

    def __init__(
        self,
        *,
        secret: str | None = None,
        jwks_url: str | None = None,
        audience: str = "authenticated",
    ) -> None:
        if not secret and not jwks_url:
            raise ValueError("SupabaseVerifier needs a secret (HS256) or a jwks_url (asymmetric).")
        self._secret = secret
        self._jwks_url = jwks_url
        self._audience = audience
        self._jwk_client: jwt.PyJWKClient | None = None

    def _client(self) -> jwt.PyJWKClient:
        if self._jwk_client is None:
            self._jwk_client = jwt.PyJWKClient(self._jwks_url)  # type: ignore[arg-type]
        return self._jwk_client

    def _verify_sync(self, token: str) -> dict[str, Any]:
        """Synchronous core — runs in a thread pool when called from async code."""
        try:
            if self._secret:
                return jwt.decode(
                    token,
                    self._secret,
                    algorithms=["HS256"],
                    audience=self._audience,
                    options={"require": ["exp", "sub"]},
                )
            # JWKS path — may make a network request on first call.
            signing_key = self._client().get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self._audience,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid Supabase token") from exc

    async def verify(self, token: str) -> dict[str, Any]:
        """Verify signature, audience, and expiry; return the claims.

        Off-loads to a thread pool so the JWKS fetch (blocking I/O in PyJWT)
        does not stall the async event loop.

        Raises:
            AuthenticationError: if the token is invalid, expired, or the
                wrong audience.
        """
        return await asyncio.to_thread(self._verify_sync, token)
