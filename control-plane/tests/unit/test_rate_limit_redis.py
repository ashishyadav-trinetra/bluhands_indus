"""Unit tests for RedisRateLimiter using a fake Redis pipeline."""

from __future__ import annotations

import pytest

from app.core.rate_limit import RedisRateLimiter


class _FakePipe:
    def __init__(self, store: dict, key_count: dict) -> None:
        self._store = store
        self._key_count = key_count
        self._ops: list = []

    def zremrangebyscore(self, *a, **k):
        self._ops.append("zrem")
        return self

    def zadd(self, key, mapping):
        self._key_count[key] = self._key_count.get(key, 0) + 1
        return self

    def zcard(self, key):
        self._ops.append(("zcard", key))
        return self

    def expire(self, *a, **k):
        return self

    async def execute(self):
        # results indexed [zrem, zadd, zcard, expire]; index 2 is the count
        last_key = list(self._key_count)[-1]
        return [0, 1, self._key_count[last_key], True]


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict = {}
        self._key_count: dict = {}

    def pipeline(self):
        return _FakePipe(self._store, self._key_count)

    async def zrem(self, key, member):
        self._key_count[key] = max(0, self._key_count.get(key, 0) - 1)


@pytest.mark.asyncio
async def test_redis_rate_limiter_allows_then_blocks() -> None:
    limiter = RedisRateLimiter(_FakeRedis())
    r1 = await limiter.hit("u:1", limit=2, window_seconds=60)
    r2 = await limiter.hit("u:1", limit=2, window_seconds=60)
    r3 = await limiter.hit("u:1", limit=2, window_seconds=60)
    assert r1.allowed and r2.allowed
    assert r3.allowed is False
    assert r3.retry_after == 60
