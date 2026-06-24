"""Unit tests for ApiKeyService."""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.security import hash_api_key
from app.services.api_key_service import ApiKeyService
from tests.fakes import InMemoryApiKeyRepo, InMemoryAudit


def _service():
    repo = InMemoryApiKeyRepo()
    return ApiKeyService(keys=repo, audit=InMemoryAudit()), repo


@pytest.mark.asyncio
async def test_create_returns_plaintext_and_stores_only_hash() -> None:
    service, repo = _service()
    org = uuid.uuid4()
    key, plaintext = await service.create_key(org, name="ci", actor="user:1")
    assert plaintext.startswith("fk_live_")
    assert key.key_hash == hash_api_key(plaintext)
    assert plaintext not in key.key_hash  # only the hash is persisted
    assert key.prefix == plaintext[:16]


@pytest.mark.asyncio
async def test_authenticate_valid_key() -> None:
    service, _ = _service()
    org = uuid.uuid4()
    _key, plaintext = await service.create_key(org, name="ci", actor="user:1")
    authed = await service.authenticate(plaintext)
    assert authed.org_id == org
    assert authed.last_used_at is not None


@pytest.mark.asyncio
async def test_authenticate_unknown_key_fails() -> None:
    service, _ = _service()
    with pytest.raises(AuthenticationError):
        await service.authenticate("fk_live_nope")


@pytest.mark.asyncio
async def test_authenticate_revoked_key_fails() -> None:
    service, _ = _service()
    org = uuid.uuid4()
    key, plaintext = await service.create_key(org, name="ci", actor="user:1")
    await service.revoke_key(org, key.id, actor="user:1")
    with pytest.raises(AuthenticationError):
        await service.authenticate(plaintext)


@pytest.mark.asyncio
async def test_revoke_wrong_org_raises_not_found() -> None:
    service, _ = _service()
    org = uuid.uuid4()
    key, _ = await service.create_key(org, name="ci", actor="user:1")
    with pytest.raises(NotFoundError):
        await service.revoke_key(uuid.uuid4(), key.id, actor="user:9")


@pytest.mark.asyncio
async def test_list_keys_scoped_to_org() -> None:
    service, _ = _service()
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    await service.create_key(org_a, name="a", actor="user:1")
    await service.create_key(org_b, name="b", actor="user:2")
    assert len(await service.list_keys(org_a)) == 1
