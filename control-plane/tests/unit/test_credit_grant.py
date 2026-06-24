"""Unit tests for CreditService.grant (top-up + idempotency)."""

from __future__ import annotations

import uuid

import pytest

from app.services.credit_service import CreditService
from tests.fakes import InMemoryCreditRepo


@pytest.mark.asyncio
async def test_grant_adds_balance() -> None:
    repo = InMemoryCreditRepo()
    org = uuid.uuid4()
    wallet = repo.seed_wallet(org, balance=10)
    service = CreditService(credits=repo)
    await service.grant(org, 40, reason="topup", idempotency_key="k1")
    assert wallet.balance == 50


@pytest.mark.asyncio
async def test_grant_is_idempotent() -> None:
    repo = InMemoryCreditRepo()
    org = uuid.uuid4()
    wallet = repo.seed_wallet(org, balance=10)
    service = CreditService(credits=repo)
    await service.grant(org, 40, reason="topup", idempotency_key="k1")
    await service.grant(org, 40, reason="topup", idempotency_key="k1")
    assert wallet.balance == 50  # second grant deduped


@pytest.mark.asyncio
async def test_grant_zero_is_noop() -> None:
    repo = InMemoryCreditRepo()
    org = uuid.uuid4()
    wallet = repo.seed_wallet(org, balance=10)
    service = CreditService(credits=repo)
    await service.grant(org, 0, reason="x", idempotency_key="k0")
    assert wallet.balance == 10
