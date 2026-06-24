"""Provider dependencies (security singletons + Redis-backed blocklist)."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.security import (
    PasswordHasher,
    RedisTokenBlocklist,
    TokenBlocklist,
    TokenManager,
    build_token_manager,
)
from app.providers.redis_client import get_redis


@lru_cache
def get_password_hasher() -> PasswordHasher:
    """Return a process-wide Argon2 password hasher."""
    return PasswordHasher()


@lru_cache
def _build_token_manager_cached() -> TokenManager:
    return build_token_manager(get_settings())


def get_token_manager() -> TokenManager:
    """Return the process-wide RS256 token manager."""
    return _build_token_manager_cached()


def get_blocklist(redis: Redis = Depends(get_redis)) -> TokenBlocklist:
    """Return a Redis-backed token blocklist."""
    return RedisTokenBlocklist(redis)


@lru_cache
def _build_supabase_verifier_cached():
    """Build the Supabase verifier once, or ``None`` if Supabase isn't configured."""
    from app.core.supabase_auth import SupabaseVerifier

    settings = get_settings()
    if not (settings.supabase_jwt_secret or settings.supabase_jwks_url):
        return None
    return SupabaseVerifier(
        secret=settings.supabase_jwt_secret,
        jwks_url=settings.supabase_jwks_url,
        audience=settings.supabase_jwt_audience,
    )


def get_supabase_verifier():
    """Return the process-wide Supabase verifier (or None if not configured)."""
    return _build_supabase_verifier_cached()


def get_app_settings() -> Settings:
    """Settings dependency (re-exported for routers)."""
    return get_settings()
