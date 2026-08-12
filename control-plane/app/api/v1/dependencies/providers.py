"""Provider dependencies (security singletons + Redis-backed blocklist)."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.rate_limit import RateLimiter, RedisRateLimiter
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


def get_rate_limiter(redis: Redis = Depends(get_redis)) -> RateLimiter:
    """Return a Redis-backed sliding-window rate limiter (shared across replicas)."""
    return RedisRateLimiter(redis)


def get_app_settings() -> Settings:
    """Settings dependency (re-exported for routers)."""
    return get_settings()
