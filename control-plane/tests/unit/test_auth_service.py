"""Unit tests for AuthService (in-memory fakes, real security primitives)."""

from __future__ import annotations

import pytest

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import TokenType
from app.db.models.enums import Role
from app.schemas.auth import RegisterRequest


def _register_payload(email: str = "owner@example.com") -> RegisterRequest:
    return RegisterRequest(
        email=email,
        password="sup3rsecret",
        full_name="Owner",
        organization_name="Acme",
    )


@pytest.mark.asyncio
async def test_register_creates_user_org_membership_and_credits(auth_components) -> None:
    service = auth_components["service"]
    user = await service.register(_register_payload())

    assert user.id is not None
    assert user.email == "owner@example.com"
    assert auth_components["users"]._by_email["owner@example.com"] is user
    # Owner membership created.
    membership = auth_components["memberships"].items[0]
    assert membership.role is Role.OWNER
    # Wallet seeded with the signup grant.
    wallet = next(iter(auth_components["wallets"].wallets.values()))
    assert wallet.balance == 100  # FORGE_FREE_CREDITS_ON_SIGNUP default
    assert "user.register" in auth_components["audit"].actions()


@pytest.mark.asyncio
async def test_register_duplicate_email_conflicts(auth_components) -> None:
    service = auth_components["service"]
    await service.register(_register_payload())
    with pytest.raises(ConflictError):
        await service.register(_register_payload())


@pytest.mark.asyncio
async def test_authenticate_success(auth_components) -> None:
    service = auth_components["service"]
    await service.register(_register_payload())
    user = await service.authenticate("owner@example.com", "sup3rsecret")
    assert user.email == "owner@example.com"
    assert "user.login" in auth_components["audit"].actions()


@pytest.mark.asyncio
async def test_authenticate_wrong_password_fails(auth_components) -> None:
    service = auth_components["service"]
    await service.register(_register_payload())
    with pytest.raises(AuthenticationError):
        await service.authenticate("owner@example.com", "wrongpass")
    assert "user.login_failed" in auth_components["audit"].actions()


@pytest.mark.asyncio
async def test_authenticate_unknown_user_fails(auth_components) -> None:
    service = auth_components["service"]
    with pytest.raises(AuthenticationError):
        await service.authenticate("nobody@example.com", "whatever123")


@pytest.mark.asyncio
async def test_refresh_rotates_and_revokes_old_token(auth_components) -> None:
    service = auth_components["service"]
    token_manager = service._tokens
    user = await service.register(_register_payload())

    first = service.issue_tokens(user)
    rotated = await service.refresh(first.refresh_token)

    # New token differs and is valid.
    assert rotated.refresh_token != first.refresh_token
    token_manager.decode(rotated.refresh_token, expected_type=TokenType.REFRESH)

    # The old refresh token is now revoked (replay rejected).
    with pytest.raises(AuthenticationError):
        await service.refresh(first.refresh_token)


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(auth_components) -> None:
    service = auth_components["service"]
    user = await service.register(_register_payload())
    tokens = service.issue_tokens(user)
    with pytest.raises(AuthenticationError):
        await service.refresh(tokens.access_token)  # wrong token type


@pytest.mark.asyncio
async def test_logout_blocklists_access_token(auth_components) -> None:
    service = auth_components["service"]
    blocklist = auth_components["blocklist"]
    user = await service.register(_register_payload())

    await service.logout(
        access_jti="access-jti-1",
        access_exp=2_000_000_000,
        refresh_token=None,
        user_id=user.id,
    )
    assert await blocklist.is_blocked("access-jti-1") is True
    assert "user.logout" in auth_components["audit"].actions()
