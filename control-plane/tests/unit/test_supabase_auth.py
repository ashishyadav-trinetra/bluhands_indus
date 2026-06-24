"""Unit tests for SupabaseVerifier (HS256 path — fully offline)."""

from __future__ import annotations

import time

import jwt
import pytest

from app.core.exceptions import AuthenticationError
from app.core.supabase_auth import SupabaseVerifier

SECRET = "test-supabase-jwt-secret"


def _token(**overrides) -> str:
    claims = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": "merchant@example.com",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, SECRET, algorithm="HS256")


# verify() is async — use pytest-asyncio for all verification tests


@pytest.mark.asyncio
async def test_verify_valid_token_returns_claims() -> None:
    claims = await SupabaseVerifier(secret=SECRET).verify(_token())
    assert claims["email"] == "merchant@example.com"
    assert claims["sub"].startswith("1111")


@pytest.mark.asyncio
async def test_rejects_bad_signature() -> None:
    forged = jwt.encode(
        {"sub": "u", "email": "a@b.com", "aud": "authenticated", "exp": int(time.time()) + 60},
        "a-different-secret",
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        await SupabaseVerifier(secret=SECRET).verify(forged)


@pytest.mark.asyncio
async def test_rejects_expired_token() -> None:
    with pytest.raises(AuthenticationError):
        await SupabaseVerifier(secret=SECRET).verify(_token(exp=int(time.time()) - 10))


@pytest.mark.asyncio
async def test_rejects_wrong_audience() -> None:
    with pytest.raises(AuthenticationError):
        await SupabaseVerifier(secret=SECRET).verify(_token(aud="some-other-aud"))


def test_requires_secret_or_jwks() -> None:
    with pytest.raises(ValueError):
        SupabaseVerifier()
