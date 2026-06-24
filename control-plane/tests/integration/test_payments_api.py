"""Integration tests for payment endpoints (checkout + webhook), offline."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import Request

from app.api.v1.dependencies.auth import get_current_user
from app.api.v1.dependencies.services import get_payment_service
from app.core.config import Settings, get_settings
from app.core.security import InMemoryTokenBlocklist  # noqa: F401 (ensures import path ok)
from app.db.models.user import User
from app.main import create_app
from app.providers.payments import PaymentFactory
from app.services.credit_service import CreditService
from app.services.payment_service import PaymentService
from tests.fakes import InMemoryAudit, InMemoryCreditRepo, InMemoryPaymentRepo

BASE = "http://test"
_SECRET = "whsec_test"
_ORG = uuid.uuid4()


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        env="development",
        jwt_private_key="x",
        jwt_public_key="x",
        prometheus_enabled=False,
        payment_provider="razorpay",
        razorpay_key_id="key",
        razorpay_key_secret="sec",
        razorpay_webhook_secret=_SECRET,
        credit_price_minor=100,
        default_currency="INR",
    )


def _admin() -> User:
    u = User(
        id=uuid.uuid4(), email="admin@x.com", full_name="Admin",
        is_active=True, is_platform_admin=True,
    )
    u.created_at = datetime.now(timezone.utc)
    return u


def _app_and_service():
    settings = _settings()
    credit_repo = InMemoryCreditRepo()
    credit_repo.seed_wallet(_ORG, balance=10)
    service = PaymentService(
        payments=InMemoryPaymentRepo(),
        credits=CreditService(credits=credit_repo),
        factory=PaymentFactory(settings),
        audit=InMemoryAudit(),
        settings=settings,
    )
    app = create_app(settings)

    async def _fake_user(request: Request) -> User:
        request.state.access_jti = "j"
        request.state.access_exp = 9999999999
        return _admin()

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_payment_service] = lambda: service
    return app, service, credit_repo


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)


@pytest.mark.asyncio
async def test_checkout_then_webhook_grants_credits() -> None:
    app, _service, credit_repo = _app_and_service()
    async with _client(app) as client:
        co = await client.post(
            f"/api/v1/orgs/{_ORG}/credits/checkout",
            json={"credits": 50},
            headers={"Authorization": "Bearer x"},
        )
        assert co.status_code == 200, co.text
        ref = co.json()["data"]["provider_ref"]

        body = json.dumps(
            {"event": "order.paid", "payload": {"order": {"entity": {"id": ref}}}}
        ).encode()
        sig = hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
        wh = await client.post(
            "/api/v1/webhooks/payments/razorpay",
            content=body,
            headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
        )
    assert wh.status_code == 200, wh.text
    assert wh.json()["data"]["applied"] is True
    assert credit_repo._org_wallets[_ORG].balance == 60


@pytest.mark.asyncio
async def test_webhook_bad_signature_returns_400() -> None:
    app, _service, _repo = _app_and_service()
    async with _client(app) as client:
        wh = await client.post(
            "/api/v1/webhooks/payments/razorpay",
            content=b'{"event":"order.paid"}',
            headers={"X-Razorpay-Signature": "bad", "Content-Type": "application/json"},
        )
    assert wh.status_code == 400
    assert wh.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"


@pytest.mark.asyncio
async def test_webhook_unknown_provider_returns_404() -> None:
    app, _service, _repo = _app_and_service()
    async with _client(app) as client:
        wh = await client.post(
            "/api/v1/webhooks/payments/paypal",
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )
    assert wh.status_code == 404
