"""Core security primitives: password hashing, RS256 JWTs, token blocklist,
and API-key hashing.

Design notes (SOLID):
- ``PasswordHasher`` and ``TokenManager`` are small, single-responsibility classes.
- ``TokenBlocklist`` is a Protocol (Interface Segregation); concrete Redis and
  in-memory implementations are interchangeable (Liskov) and injected (DIP).
"""

from __future__ import annotations

import enum
import hashlib
import secrets
import time
import uuid
from typing import Any, Protocol, runtime_checkable

import jwt
from argon2 import PasswordHasher as _Argon2Hasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import Settings
from app.core.exceptions import AuthenticationError

# ─────────────────────────────────────────────────────────────────────────────
# Passwords (Argon2id — current OWASP-recommended default)
# ─────────────────────────────────────────────────────────────────────────────


class PasswordHasher:
    """Hash and verify passwords using Argon2id."""

    def __init__(self) -> None:
        self._hasher = _Argon2Hasher()

    def hash(self, password: str) -> str:
        """Return an Argon2id hash for ``password``."""
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        """Return True if ``password`` matches ``password_hash``.

        Never raises on mismatch — returns False instead (no information leak).
        """
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError, ValueError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """True if the hash should be upgraded to current parameters."""
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except (InvalidHashError, ValueError):
            return True


# ─────────────────────────────────────────────────────────────────────────────
# JSON Web Tokens (RS256, asymmetric)
# ─────────────────────────────────────────────────────────────────────────────


class TokenType(str, enum.Enum):
    """Distinguishes access from refresh tokens to prevent cross-use."""

    ACCESS = "access"
    REFRESH = "refresh"


_ALGORITHM = "RS256"


class TokenManager:
    """Create and verify RS256 JWTs.

    Args:
        private_key: PEM-encoded RSA private key (signing).
        public_key: PEM-encoded RSA public key (verification).
        issuer: Expected ``iss`` claim.
        audience: Expected ``aud`` claim.
        access_ttl_seconds: Access token lifetime.
        refresh_ttl_seconds: Refresh token lifetime.
    """

    def __init__(
        self,
        *,
        private_key: str,
        public_key: str,
        issuer: str,
        audience: str,
        access_ttl_seconds: int,
        refresh_ttl_seconds: int,
    ) -> None:
        self._private_key = private_key
        self._public_key = public_key
        self._issuer = issuer
        self._audience = audience
        self._access_ttl = access_ttl_seconds
        self._refresh_ttl = refresh_ttl_seconds

    def create_access_token(
        self, subject: str, *, claims: dict[str, Any] | None = None
    ) -> tuple[str, str]:
        """Create an access token. Returns ``(token, jti)``."""
        return self._create(subject, TokenType.ACCESS, self._access_ttl, claims)

    def create_refresh_token(
        self, subject: str, *, claims: dict[str, Any] | None = None
    ) -> tuple[str, str]:
        """Create a refresh token. Returns ``(token, jti)``."""
        return self._create(subject, TokenType.REFRESH, self._refresh_ttl, claims)

    def decode(self, token: str, *, expected_type: TokenType) -> dict[str, Any]:
        """Verify a token's signature, claims, and type. Return the payload.

        Raises:
            AuthenticationError: if invalid, expired, or the wrong type.
        """
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._public_key,
                algorithms=[_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "jti", "type"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid or expired token") from exc

        if payload.get("type") != expected_type.value:
            raise AuthenticationError("Incorrect token type")
        return payload

    def _create(
        self,
        subject: str,
        token_type: TokenType,
        ttl: int,
        claims: dict[str, Any] | None,
    ) -> tuple[str, str]:
        now = int(time.time())
        jti = uuid.uuid4().hex
        payload: dict[str, Any] = {
            "sub": subject,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "nbf": now,
            "exp": now + ttl,
            "jti": jti,
            "type": token_type.value,
        }
        if claims:
            # Reserved claims cannot be overridden by callers.
            reserved = {"sub", "iss", "aud", "iat", "nbf", "exp", "jti", "type"}
            payload.update({k: v for k, v in claims.items() if k not in reserved})
        token = jwt.encode(payload, self._private_key, algorithm=_ALGORITHM)
        return token, jti


def build_token_manager(settings: Settings) -> TokenManager:
    """Factory: construct a TokenManager from application settings."""
    return TokenManager(
        private_key=settings.resolve_jwt_private_key(),
        public_key=settings.resolve_jwt_public_key(),
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        access_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_ttl_seconds=settings.refresh_token_ttl_seconds,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Token blocklist (logout / forced revocation)
# ─────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class TokenBlocklist(Protocol):
    """Interface for storing revoked token ids (``jti``)."""

    async def block(self, jti: str, *, ttl_seconds: int) -> None:
        """Mark a ``jti`` as revoked for ``ttl_seconds`` (its remaining life)."""
        ...

    async def is_blocked(self, jti: str) -> bool:
        """Return True if the ``jti`` has been revoked."""
        ...


class InMemoryTokenBlocklist:
    """In-process blocklist for tests and single-process dev.

    Not suitable for multi-process production — use ``RedisTokenBlocklist``.
    """

    def __init__(self) -> None:
        self._store: dict[str, float] = {}

    async def block(self, jti: str, *, ttl_seconds: int) -> None:
        self._store[jti] = time.time() + ttl_seconds

    async def is_blocked(self, jti: str) -> bool:
        expiry = self._store.get(jti)
        if expiry is None:
            return False
        if expiry < time.time():
            self._store.pop(jti, None)
            return False
        return True


class RedisTokenBlocklist:
    """Redis-backed blocklist. Keys auto-expire with the token's TTL.

    Args:
        client: An async Redis client (``redis.asyncio.Redis``).
        namespace: Key prefix to isolate blocklist entries.
    """

    def __init__(self, client: Any, *, namespace: str = "blocklist") -> None:
        self._client = client
        self._namespace = namespace

    def _key(self, jti: str) -> str:
        return f"{self._namespace}:{jti}"

    async def block(self, jti: str, *, ttl_seconds: int) -> None:
        await self._client.set(self._key(jti), "1", ex=max(ttl_seconds, 1))

    async def is_blocked(self, jti: str) -> bool:
        return bool(await self._client.exists(self._key(jti)))


# ─────────────────────────────────────────────────────────────────────────────
# API keys (machine auth) — store only the SHA-256 hash
# ─────────────────────────────────────────────────────────────────────────────

_API_KEY_PREFIX = "fk"


def hash_api_key(plaintext: str) -> str:
    """Return the SHA-256 hex digest of an API key (what we store)."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_api_key(*, live: bool = True) -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        ``(plaintext, prefix, key_hash)``. The plaintext is shown to the user
        once and never stored; only ``key_hash`` is persisted.
    """
    env_tag = "live" if live else "test"
    secret = secrets.token_urlsafe(32)
    plaintext = f"{_API_KEY_PREFIX}_{env_tag}_{secret}"
    prefix = plaintext[:16]
    return plaintext, prefix, hash_api_key(plaintext)
