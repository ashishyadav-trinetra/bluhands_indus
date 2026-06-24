"""Sliding-window rate limiting (Strategy pattern).

``RateLimiter`` is the interface; a Redis implementation backs production
(shared across processes) and an in-memory one backs tests. Both use a
sliding-window-log algorithm keyed by an arbitrary identity (user id or IP).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RateLimiter(Protocol):
    """Interface for sliding-window rate limiters."""

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        """Record a hit for ``key`` and report whether it is allowed."""
        ...


class RateLimitResult:
    """Outcome of a rate-limit check."""

    def __init__(self, *, allowed: bool, remaining: int, retry_after: int) -> None:
        self.allowed = allowed
        self.remaining = remaining
        self.retry_after = retry_after


class InMemoryRateLimiter:
    """Process-local sliding-window limiter (tests / single-process dev)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.monotonic()
        window_start = now - window_seconds
        bucket = self._hits[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = int(bucket[0] + window_seconds - now) + 1
            return RateLimitResult(allowed=False, remaining=0, retry_after=max(retry_after, 1))
        bucket.append(now)
        return RateLimitResult(allowed=True, remaining=limit - len(bucket), retry_after=0)


class RedisRateLimiter:
    """Redis sorted-set sliding-window limiter (shared across processes).

    Args:
        client: An async Redis client.
        namespace: Key prefix.
    """

    def __init__(self, client: Any, *, namespace: str = "ratelimit") -> None:
        self._client = client
        self._namespace = namespace

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        redis_key = f"{self._namespace}:{key}"
        now = time.time()
        window_start = now - window_seconds
        member = f"{now}:{id(object())}"

        pipe = self._client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zadd(redis_key, {member: now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window_seconds)
        results = await pipe.execute()
        count = int(results[2])

        if count > limit:
            await self._client.zrem(redis_key, member)
            return RateLimitResult(allowed=False, remaining=0, retry_after=window_seconds)
        return RateLimitResult(allowed=True, remaining=limit - count, retry_after=0)
