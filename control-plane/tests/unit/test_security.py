"""Unit tests for core security primitives."""

from __future__ import annotations

import pytest

from app.core.exceptions import AuthenticationError
from app.core.security import (
    InMemoryTokenBlocklist,
    PasswordHasher,
    TokenManager,
    TokenType,
    generate_api_key,
    hash_api_key,
)

# --- Password hashing -------------------------------------------------------


def test_password_hash_and_verify_roundtrip() -> None:
    hasher = PasswordHasher()
    digest = hasher.hash("correct horse battery staple")
    assert digest != "correct horse battery staple"
    assert hasher.verify("correct horse battery staple", digest) is True


def test_password_verify_rejects_wrong_password() -> None:
    hasher = PasswordHasher()
    digest = hasher.hash("s3cret")
    assert hasher.verify("wrong", digest) is False


def test_password_verify_handles_garbage_hash_without_raising() -> None:
    hasher = PasswordHasher()
    assert hasher.verify("anything", "not-a-valid-hash") is False


# --- JWTs -------------------------------------------------------------------


def test_access_token_roundtrip(token_manager: TokenManager) -> None:
    token, jti = token_manager.create_access_token("user-123", claims={"role": "owner"})
    payload = token_manager.decode(token, expected_type=TokenType.ACCESS)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "owner"
    assert payload["jti"] == jti
    assert payload["type"] == "access"


def test_refresh_token_roundtrip(token_manager: TokenManager) -> None:
    token, _ = token_manager.create_refresh_token("user-123")
    payload = token_manager.decode(token, expected_type=TokenType.REFRESH)
    assert payload["type"] == "refresh"


def test_decode_rejects_wrong_token_type(token_manager: TokenManager) -> None:
    access, _ = token_manager.create_access_token("u")
    with pytest.raises(AuthenticationError):
        token_manager.decode(access, expected_type=TokenType.REFRESH)


def test_decode_rejects_tampered_token(token_manager: TokenManager) -> None:
    token, _ = token_manager.create_access_token("u")
    tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
    with pytest.raises(AuthenticationError):
        token_manager.decode(tampered, expected_type=TokenType.ACCESS)


def test_decode_rejects_expired_token(rsa_keypair: tuple[str, str]) -> None:
    private_pem, public_pem = rsa_keypair
    manager = TokenManager(
        private_key=private_pem,
        public_key=public_pem,
        issuer="forge-test",
        audience="forge-test-clients",
        access_ttl_seconds=-1,  # already expired
        refresh_ttl_seconds=-1,
    )
    token, _ = manager.create_access_token("u")
    with pytest.raises(AuthenticationError):
        manager.decode(token, expected_type=TokenType.ACCESS)


def test_caller_cannot_override_reserved_claims(token_manager: TokenManager) -> None:
    token, _ = token_manager.create_access_token("real-subject", claims={"sub": "spoofed"})
    payload = token_manager.decode(token, expected_type=TokenType.ACCESS)
    assert payload["sub"] == "real-subject"


# --- Token blocklist --------------------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_blocklist() -> None:
    blocklist = InMemoryTokenBlocklist()
    assert await blocklist.is_blocked("jti-1") is False
    await blocklist.block("jti-1", ttl_seconds=60)
    assert await blocklist.is_blocked("jti-1") is True


@pytest.mark.asyncio
async def test_in_memory_blocklist_expiry() -> None:
    blocklist = InMemoryTokenBlocklist()
    await blocklist.block("jti-2", ttl_seconds=-1)  # already expired
    assert await blocklist.is_blocked("jti-2") is False


# --- API keys ---------------------------------------------------------------


def test_generate_api_key_returns_hash_not_plaintext() -> None:
    plaintext, prefix, key_hash = generate_api_key(live=True)
    assert plaintext.startswith("fk_live_")
    assert prefix == plaintext[:16]
    assert key_hash == hash_api_key(plaintext)
    assert plaintext not in key_hash  # only the hash is storable


def test_api_key_hash_is_deterministic() -> None:
    assert hash_api_key("abc") == hash_api_key("abc")
    assert hash_api_key("abc") != hash_api_key("abd")
