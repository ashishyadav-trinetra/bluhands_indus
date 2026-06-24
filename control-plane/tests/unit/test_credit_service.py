"""Unit tests for CreditService.

All tests use InMemoryCreditRepo — no DB, no transactions.
Tests cover: reserve, capture, refund, idempotency replay, and edge cases.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import InsufficientCreditsError
from app.services.credit_service import CreditService
from tests.fakes import InMemoryCreditRepo


def _svc(repo: InMemoryCreditRepo) -> CreditService:
    return CreditService(credits=repo)


def _ids() -> tuple[uuid.UUID, uuid.UUID]:
    return uuid.uuid4(), uuid.uuid4()  # org_id, build_run_id


# ---------------------------------------------------------------------------
# reserve
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reserve_deducts_balance_and_increases_reserved():
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()
    wallet = repo.seed_wallet(org_id, balance=100, reserved=0)

    await _svc(repo).reserve(org_id, 10, build_run_id=build_id, idempotency_key=f"reserve:{build_id}")

    assert wallet.balance == 90
    assert wallet.reserved == 10


@pytest.mark.asyncio
async def test_reserve_writes_ledger_entry():
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()
    repo.seed_wallet(org_id, balance=100)
    key = f"reserve:{build_id}"

    await _svc(repo).reserve(org_id, 10, build_run_id=build_id, idempotency_key=key)

    assert repo._txns_by_key[key] is not None
    assert repo._reserve_by_build[build_id] is not None


@pytest.mark.asyncio
async def test_reserve_raises_if_insufficient_credits():
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()
    repo.seed_wallet(org_id, balance=5)

    with pytest.raises(InsufficientCreditsError):
        await _svc(repo).reserve(org_id, 10, build_run_id=build_id, idempotency_key=f"reserve:{build_id}")


@pytest.mark.asyncio
async def test_reserve_raises_if_no_wallet():
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()

    with pytest.raises(InsufficientCreditsError):
        await _svc(repo).reserve(org_id, 10, build_run_id=build_id, idempotency_key=f"reserve:{build_id}")


@pytest.mark.asyncio
async def test_reserve_idempotent_replay_is_no_op():
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()
    wallet = repo.seed_wallet(org_id, balance=100)
    key = f"reserve:{build_id}"

    await _svc(repo).reserve(org_id, 10, build_run_id=build_id, idempotency_key=key)
    await _svc(repo).reserve(org_id, 10, build_run_id=build_id, idempotency_key=key)

    # Second call is a no-op — balance deducted only once.
    assert wallet.balance == 90
    assert wallet.reserved == 10


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_capture_clears_reserved():
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()
    wallet = repo.seed_wallet(org_id, balance=90, reserved=10)
    # Seed a reserve transaction so capture knows the amount.
    from app.db.models.credit import CreditTransaction
    from app.db.models.enums import CreditTxnKind
    reserve_txn = CreditTransaction(
        wallet_id=wallet.id, build_run_id=build_id,
        kind=CreditTxnKind.RESERVE, amount=-10,
        reason="reserve", idempotency_key=f"reserve:{build_id}",
    )
    await repo.add_transaction(reserve_txn)

    await _svc(repo).capture(org_id, build_run_id=build_id, idempotency_key=f"capture:{build_id}")

    assert wallet.reserved == 0
    assert wallet.balance == 90  # balance unchanged (was already deducted at reserve)


@pytest.mark.asyncio
async def test_capture_idempotent_replay_is_no_op():
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()
    wallet = repo.seed_wallet(org_id, balance=90, reserved=10)
    from app.db.models.credit import CreditTransaction
    from app.db.models.enums import CreditTxnKind
    await repo.add_transaction(CreditTransaction(
        wallet_id=wallet.id, build_run_id=build_id,
        kind=CreditTxnKind.RESERVE, amount=-10,
        reason="reserve", idempotency_key=f"reserve:{build_id}",
    ))
    key = f"capture:{build_id}"

    await _svc(repo).capture(org_id, build_run_id=build_id, idempotency_key=key)
    await _svc(repo).capture(org_id, build_run_id=build_id, idempotency_key=key)

    assert wallet.reserved == 0  # not negative


@pytest.mark.asyncio
async def test_capture_no_wallet_is_silent():
    """Capture on a deleted wallet must not raise (ops idempotency)."""
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()
    # No wallet seeded.
    await _svc(repo).capture(org_id, build_run_id=build_id, idempotency_key=f"capture:{build_id}")


# ---------------------------------------------------------------------------
# refund
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refund_restores_balance():
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()
    wallet = repo.seed_wallet(org_id, balance=90, reserved=10)
    from app.db.models.credit import CreditTransaction
    from app.db.models.enums import CreditTxnKind
    await repo.add_transaction(CreditTransaction(
        wallet_id=wallet.id, build_run_id=build_id,
        kind=CreditTxnKind.RESERVE, amount=-10,
        reason="reserve", idempotency_key=f"reserve:{build_id}",
    ))

    await _svc(repo).refund(org_id, build_run_id=build_id, idempotency_key=f"refund:{build_id}")

    assert wallet.balance == 100  # 90 + 10 returned
    assert wallet.reserved == 0   # cleared


@pytest.mark.asyncio
async def test_refund_idempotent_replay_is_no_op():
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()
    wallet = repo.seed_wallet(org_id, balance=90, reserved=10)
    from app.db.models.credit import CreditTransaction
    from app.db.models.enums import CreditTxnKind
    await repo.add_transaction(CreditTransaction(
        wallet_id=wallet.id, build_run_id=build_id,
        kind=CreditTxnKind.RESERVE, amount=-10,
        reason="reserve", idempotency_key=f"reserve:{build_id}",
    ))
    key = f"refund:{build_id}"

    await _svc(repo).refund(org_id, build_run_id=build_id, idempotency_key=key)
    await _svc(repo).refund(org_id, build_run_id=build_id, idempotency_key=key)

    assert wallet.balance == 100  # restored only once


@pytest.mark.asyncio
async def test_refund_no_wallet_is_silent():
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()
    await _svc(repo).refund(org_id, build_run_id=build_id, idempotency_key=f"refund:{build_id}")


@pytest.mark.asyncio
async def test_refund_no_reserve_txn_is_no_op_on_balance():
    """If reserve was never written (e.g. build was free), refund changes nothing."""
    repo = InMemoryCreditRepo()
    org_id, build_id = _ids()
    wallet = repo.seed_wallet(org_id, balance=100, reserved=0)

    await _svc(repo).refund(org_id, build_run_id=build_id, idempotency_key=f"refund:{build_id}")

    assert wallet.balance == 100
    assert wallet.reserved == 0
