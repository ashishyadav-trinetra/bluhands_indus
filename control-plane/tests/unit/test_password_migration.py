"""Transparent password-hash upgrade on login.

``needs_rehash`` had no call site until now. Wiring it into ``authenticate``
means we can raise Argon2 cost parameters later and existing hashes upgrade
themselves as users sign in, instead of locking anyone out.
"""

from __future__ import annotations

import pytest
from argon2 import PasswordHasher as _Argon2Hasher

from app.core.exceptions import AuthenticationError
from app.core.security import PasswordHasher
from app.db.models.user import User


def _weak_hash(password: str) -> str:
    """An Argon2id hash made with deliberately outdated (cheap) parameters."""
    return _Argon2Hasher(time_cost=1, memory_size=8, parallelism=1).hash(password)


# --- PasswordHasher ---------------------------------------------------------


def test_argon2_roundtrip() -> None:
    hasher = PasswordHasher()
    stored = hasher.hash("correct horse battery staple")

    assert stored.startswith("$argon2")
    assert hasher.verify("correct horse battery staple", stored)
    assert not hasher.verify("wrong password", stored)
    assert not hasher.needs_rehash(stored)


def test_outdated_parameters_are_flagged_for_rehash() -> None:
    hasher = PasswordHasher()
    stored = _weak_hash("correct horse battery staple")

    assert hasher.verify("correct horse battery staple", stored)
    assert hasher.needs_rehash(stored)


def test_malformed_hash_is_false_not_an_exception() -> None:
    hasher = PasswordHasher()

    assert not hasher.verify("anything", "garbage")
    assert hasher.needs_rehash("garbage")


# --- The upgrade happens on login -------------------------------------------


@pytest.mark.asyncio
async def test_login_upgrades_an_outdated_hash(auth_components) -> None:
    service = auth_components["service"]
    users = auth_components["users"]

    user = User(
        email="stale@example.com",
        password_hash=_weak_hash("their-password"),
        is_active=True,
        is_platform_admin=False,
    )
    await users.add(user)
    stale = user.password_hash

    await service.authenticate("stale@example.com", "their-password")

    assert user.password_hash != stale, "hash was not upgraded"
    assert not PasswordHasher().needs_rehash(user.password_hash)


@pytest.mark.asyncio
async def test_upgraded_hash_still_authenticates_next_time(auth_components) -> None:
    """The upgrade must not lock the user out of their own password."""
    service = auth_components["service"]
    users = auth_components["users"]

    user = User(
        email="twice@example.com",
        password_hash=_weak_hash("their-password"),
        is_active=True,
        is_platform_admin=False,
    )
    await users.add(user)

    await service.authenticate("twice@example.com", "their-password")
    again = await service.authenticate("twice@example.com", "their-password")

    assert again.id == user.id


@pytest.mark.asyncio
async def test_wrong_password_does_not_upgrade_the_hash(auth_components) -> None:
    service = auth_components["service"]
    users = auth_components["users"]

    user = User(
        email="attacked@example.com",
        password_hash=_weak_hash("their-password"),
        is_active=True,
        is_platform_admin=False,
    )
    await users.add(user)
    stale = user.password_hash

    with pytest.raises(AuthenticationError):
        await service.authenticate("attacked@example.com", "guessing")

    assert user.password_hash == stale
