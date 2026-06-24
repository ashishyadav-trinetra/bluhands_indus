"""Unit tests for payment provider Strategy (HMAC verification + parsing)."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.providers.payments import (
    PaymentFactory,
    RazorpayPaymentProvider,
    StripePaymentProvider,
)


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_razorpay_verify_good_and_bad() -> None:
    provider = RazorpayPaymentProvider(key_id="k", key_secret="s", webhook_secret="whsec")
    body = b'{"event":"order.paid"}'
    good = _sign("whsec", body)
    assert provider.verify_signature(raw_body=body, signature_header=good) is True
    assert provider.verify_signature(raw_body=body, signature_header="deadbeef") is False
    assert provider.verify_signature(raw_body=body, signature_header=None) is False


def test_razorpay_parse_confirmed_event() -> None:
    provider = RazorpayPaymentProvider(key_id="k", key_secret="s", webhook_secret="w")
    body = json.dumps(
        {"event": "order.paid", "payload": {"order": {"entity": {"id": "order_abc"}}}}
    ).encode()
    event = provider.parse_event(raw_body=body)
    assert event.provider_ref == "order_abc"
    assert event.confirmed is True


def test_stripe_verify_good_and_bad() -> None:
    provider = StripePaymentProvider(secret_key="sk", webhook_secret="whsec")
    body = b'{"type":"checkout.session.completed"}'
    ts = "1700000000"
    sig = _sign("whsec", f"{ts}.".encode() + body)
    header = f"t={ts},v1={sig}"
    assert provider.verify_signature(raw_body=body, signature_header=header) is True
    assert provider.verify_signature(raw_body=body, signature_header=f"t={ts},v1=bad") is False
    assert provider.verify_signature(raw_body=body, signature_header=None) is False


def test_stripe_parse_confirmed_event() -> None:
    provider = StripePaymentProvider(secret_key="sk", webhook_secret="w")
    body = json.dumps(
        {"type": "checkout.session.completed", "data": {"object": {"id": "cs_123"}}}
    ).encode()
    event = provider.parse_event(raw_body=body)
    assert event.provider_ref == "cs_123"
    assert event.confirmed is True


def test_factory_unknown_provider_raises(settings) -> None:
    with pytest.raises(ValueError):
        PaymentFactory(settings).get("paypal")
