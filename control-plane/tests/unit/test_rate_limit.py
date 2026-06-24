"""Unit tests for the in-memory sliding-window rate limiter."""

from __future__ import annotations

import pytest

from app.core.rate_limit import InMemoryRateLimiter


@pytest.mark.asyncio
async def test_allows_up_to_limit_then_blocks() -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        result = await limiter.hit("user:1", limit=3, window_seconds=60)
        assert result.allowed is True
    blocked = await limiter.hit("user:1", limit=3, window_seconds=60)
    assert blocked.allowed is False
    assert blocked.retry_after >= 1


@pytest.mark.asyncio
async def test_keys_are_independent() -> None:
    limiter = InMemoryRateLimiter()
    await limiter.hit("user:1", limit=1, window_seconds=60)
    other = await limiter.hit("user:2", limit=1, window_seconds=60)
    assert other.allowed is True
