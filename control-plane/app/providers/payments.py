"""Payment providers (Strategy + Factory).

Webhook signature verification is implemented in full (HMAC-SHA256) — this is the
money-security-critical path. Checkout-session creation returns a provider
reference; in production the real provider SDK call happens inside
``create_checkout`` (the integration seam, to be wrapped in a circuit breaker).
We avoid hard SDK dependencies so the security logic stays testable offline.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.core.config import PaymentProvider as ProviderName
from app.core.config import Settings
from app.core.exceptions import AppError


class PaymentConfigError(AppError):
    """Provider is not configured (missing secret)."""

    code = "PAYMENT_PROVIDER_UNCONFIGURED"
    http_status = 503


class WebhookVerificationError(AppError):
    """Webhook signature failed verification."""

    code = "WEBHOOK_SIGNATURE_INVALID"
    http_status = 400


@dataclass(frozen=True)
class CheckoutIntent:
    """Result of creating a checkout session with a provider."""

    provider_ref: str
    checkout_url: str


@dataclass(frozen=True)
class WebhookEvent:
    """Normalized webhook event extracted from a provider payload."""

    provider_ref: str
    confirmed: bool
    raw_status: str


@runtime_checkable
class PaymentProvider(Protocol):
    """Interface every payment provider implements (Liskov-substitutable)."""

    name: str

    def create_checkout(
        self, *, amount_minor: int, currency: str, metadata: dict[str, str]
    ) -> CheckoutIntent: ...

    def verify_signature(self, *, raw_body: bytes, signature_header: str | None) -> bool: ...

    def parse_event(self, *, raw_body: bytes) -> WebhookEvent: ...


def _hmac_sha256_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


class RazorpayPaymentProvider:
    """Razorpay: webhook signature = HMAC-SHA256(secret, raw_body) hex."""

    name = ProviderName.RAZORPAY.value

    def __init__(self, *, key_id: str | None, key_secret: str | None, webhook_secret: str | None) -> None:
        self._key_id = key_id
        self._key_secret = key_secret
        self._webhook_secret = webhook_secret

    def create_checkout(
        self, *, amount_minor: int, currency: str, metadata: dict[str, str]
    ) -> CheckoutIntent:
        if not self._key_id:
            raise PaymentConfigError("Razorpay is not configured.")
        # PROD INTEGRATION SEAM: call Razorpay Orders API here and use its order id.
        provider_ref = f"order_{secrets.token_hex(12)}"
        return CheckoutIntent(
            provider_ref=provider_ref,
            checkout_url=f"https://checkout.razorpay.com/v1/checkout/{provider_ref}",
        )

    def verify_signature(self, *, raw_body: bytes, signature_header: str | None) -> bool:
        if not self._webhook_secret or not signature_header:
            return False
        expected = _hmac_sha256_hex(self._webhook_secret, raw_body)
        return hmac.compare_digest(expected, signature_header.strip())

    def parse_event(self, *, raw_body: bytes) -> WebhookEvent:
        data = json.loads(raw_body.decode("utf-8"))
        event = data.get("event", "")
        entity = (
            data.get("payload", {})
            .get("order", {})
            .get("entity", {})
        )
        provider_ref = entity.get("id", "")
        confirmed = event in {"order.paid", "payment.captured"}
        return WebhookEvent(provider_ref=provider_ref, confirmed=confirmed, raw_status=event)


class StripePaymentProvider:
    """Stripe: header ``t=<ts>,v1=<sig>``; signed_payload = ``<ts>.<body>``."""

    name = ProviderName.STRIPE.value

    def __init__(self, *, secret_key: str | None, webhook_secret: str | None) -> None:
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret

    def create_checkout(
        self, *, amount_minor: int, currency: str, metadata: dict[str, str]
    ) -> CheckoutIntent:
        if not self._secret_key:
            raise PaymentConfigError("Stripe is not configured.")
        # PROD INTEGRATION SEAM: call Stripe Checkout Sessions API here.
        provider_ref = f"cs_test_{secrets.token_hex(12)}"
        return CheckoutIntent(
            provider_ref=provider_ref,
            checkout_url=f"https://checkout.stripe.com/c/pay/{provider_ref}",
        )

    def verify_signature(self, *, raw_body: bytes, signature_header: str | None) -> bool:
        if not self._webhook_secret or not signature_header:
            return False
        parts = dict(
            p.split("=", 1) for p in signature_header.split(",") if "=" in p
        )
        timestamp, sig = parts.get("t"), parts.get("v1")
        if not timestamp or not sig:
            return False
        signed_payload = f"{timestamp}.".encode() + raw_body
        expected = _hmac_sha256_hex(self._webhook_secret, signed_payload)
        return hmac.compare_digest(expected, sig)

    def parse_event(self, *, raw_body: bytes) -> WebhookEvent:
        data = json.loads(raw_body.decode("utf-8"))
        etype = data.get("type", "")
        obj = data.get("data", {}).get("object", {})
        provider_ref = obj.get("id", "")
        confirmed = etype in {"checkout.session.completed", "payment_intent.succeeded"}
        return WebhookEvent(provider_ref=provider_ref, confirmed=confirmed, raw_status=etype)


class PaymentFactory:
    """Builds the configured payment provider(s) (Factory pattern)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get(self, name: str) -> PaymentProvider:
        """Return a provider by name; raises ValueError on unknown provider."""
        if name == ProviderName.RAZORPAY.value:
            return RazorpayPaymentProvider(
                key_id=self._settings.razorpay_key_id,
                key_secret=self._settings.razorpay_key_secret,
                webhook_secret=self._settings.razorpay_webhook_secret,
            )
        if name == ProviderName.STRIPE.value:
            return StripePaymentProvider(
                secret_key=self._settings.stripe_secret_key,
                webhook_secret=self._settings.stripe_webhook_secret,
            )
        raise ValueError(f"Unknown payment provider: {name}")

    def default(self) -> PaymentProvider:
        """Return the configured default provider."""
        return self.get(self._settings.payment_provider.value)
