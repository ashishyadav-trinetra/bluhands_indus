"""Unit tests for PaymentService (checkout + signature-verified webhook grant)."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest

from app.core.config import Settings
from app.db.models.enums import PaymentStatus
from app.providers.payments import PaymentFactory, WebhookVerificationError
from app.services.credit_service import CreditService
from app.services.payment_service import PaymentService
from tests.fakes import InMemoryAudit, InMemoryCreditRepo, InMemoryPaymentRepo

_SECRET = "whsec_test"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        payment_provider="razorpay",
        razorpay_key_id="key",
        razorpay_key_secret="sec",
        razorpay_webhook_secret=_SECRET,
        credit_price_minor=100,
        default_currency="INR",
    )


def _build_service(credit_repo: InMemoryCreditRepo) -> tuple[PaymentService, InMemoryPaymentRepo]:
    payments = InMemoryPaymentRepo()
    service = PaymentService(
        payments=payments,
        credits=CreditService(credits=credit_repo),
        factory=PaymentFactory(_settings()),
        audit=InMemoryAudit(),
        settings=_settings(),
    )
    return service, payments


def _signed_confirmed_body(provider_ref: str) -> tuple[bytes, str]:
    body = json.dumps(
        {"event": "order.paid", "payload": {"order": {"entity": {"id": provider_ref}}}}
    ).encode()
    sig = hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return body, sig


@pytest.mark.asyncio
async def test_create_checkout_creates_pending_payment() -> None:
    repo = InMemoryCreditRepo()
    org = uuid.uuid4()
    repo.seed_wallet(org, balance=0)
    service, payments = _build_service(repo)

    result = await service.create_checkout(org, credits=50)
    assert result.payment.status == PaymentStatus.PENDING
    assert result.payment.credits_granted == 50
    assert result.amount_minor == 5000
    assert result.checkout_url
    assert await payments.get_by_provider_ref(result.payment.provider_ref) is not None


@pytest.mark.asyncio
async def test_webhook_confirmed_grants_credits_once() -> None:
    repo = InMemoryCreditRepo()
    org = uuid.uuid4()
    wallet = repo.seed_wallet(org, balance=10)
    service, _ = _build_service(repo)

    checkout = await service.create_checkout(org, credits=50)
    ref = checkout.payment.provider_ref
    body, sig = _signed_confirmed_body(ref)

    r1 = await service.handle_webhook("razorpay", raw_body=body, signature_header=sig)
    assert r1.applied is True
    assert wallet.balance == 60  # 10 + 50 granted
    assert checkout.payment.status == PaymentStatus.CONFIRMED

    # Replay: same signed webhook must NOT double-grant.
    r2 = await service.handle_webhook("razorpay", raw_body=body, signature_header=sig)
    assert r2.applied is False
    assert wallet.balance == 60


@pytest.mark.asyncio
async def test_webhook_bad_signature_raises() -> None:
    repo = InMemoryCreditRepo()
    org = uuid.uuid4()
    repo.seed_wallet(org, balance=0)
    service, _ = _build_service(repo)
    checkout = await service.create_checkout(org, credits=10)
    body, _ = _signed_confirmed_body(checkout.payment.provider_ref)

    with pytest.raises(WebhookVerificationError):
        await service.handle_webhook("razorpay", raw_body=body, signature_header="bad")


@pytest.mark.asyncio
async def test_webhook_unknown_ref_is_noop() -> None:
    repo = InMemoryCreditRepo()
    org = uuid.uuid4()
    repo.seed_wallet(org, balance=5)
    service, _ = _build_service(repo)
    body, sig = _signed_confirmed_body("order_does_not_exist")
    result = await service.handle_webhook("razorpay", raw_body=body, signature_header=sig)
    assert result.applied is False


@pytest.mark.asyncio
async def test_webhook_unknown_provider_raises() -> None:
    repo = InMemoryCreditRepo()
    service, _ = _build_service(repo)
    with pytest.raises(ValueError):
        await service.handle_webhook("paypal", raw_body=b"{}", signature_header="x")
