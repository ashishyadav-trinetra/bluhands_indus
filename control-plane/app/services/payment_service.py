"""PaymentService — checkout intents + signature-verified webhook credit grants.

Money-safety rules (CODING-STANDARDS §6):
- Credits are granted ONLY after a signature-verified webhook confirms payment.
- Idempotent: dedupe by provider_ref (unique Payment row) + a grant idempotency
  key, so webhook retries/replays never double-grant.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.core.config import Settings
from app.db.models.enums import PaymentStatus
from app.db.models.payment import Payment
from app.providers.payments import PaymentFactory, WebhookVerificationError
from app.services.protocols import (
    AuditLoggerProtocol,
    CreditGranterProtocol,
    PaymentRepositoryProtocol,
)


@dataclass(frozen=True)
class CheckoutResult:
    """A created checkout session."""

    payment: Payment
    checkout_url: str
    amount_minor: int


@dataclass(frozen=True)
class WebhookResult:
    """Outcome of processing a webhook."""

    applied: bool


class PaymentService:
    """Creates checkout sessions and processes provider webhooks."""

    def __init__(
        self,
        *,
        payments: PaymentRepositoryProtocol,
        credits: CreditGranterProtocol,
        factory: PaymentFactory,
        audit: AuditLoggerProtocol,
        settings: Settings,
    ) -> None:
        self._payments = payments
        self._credits = credits
        self._factory = factory
        self._audit = audit
        self._settings = settings

    async def create_checkout(
        self,
        org_id: uuid.UUID,
        *,
        credits: int,
        currency: str | None = None,
        ip: str | None = None,
    ) -> CheckoutResult:
        """Create a provider checkout session and a PENDING payment row."""
        provider = self._factory.default()
        currency = (currency or self._settings.default_currency).upper()
        amount_minor = credits * self._settings.credit_price_minor

        intent = provider.create_checkout(
            amount_minor=amount_minor,
            currency=currency,
            metadata={"org_id": str(org_id), "credits": str(credits)},
        )
        payment = Payment(
            org_id=org_id,
            provider=provider.name,
            provider_ref=intent.provider_ref,
            status=PaymentStatus.PENDING,
            credits_granted=credits,
            amount=Decimal(amount_minor) / Decimal(100),
            currency=currency,
        )
        await self._payments.add(payment)
        await self._audit.record(
            AuditEvent(
                actor=f"org:{org_id}",
                org_id=org_id,
                action="payment.checkout_created",
                target=intent.provider_ref,
                ip=ip,
            )
        )
        return CheckoutResult(payment=payment, checkout_url=intent.checkout_url, amount_minor=amount_minor)

    async def handle_webhook(
        self, provider_name: str, *, raw_body: bytes, signature_header: str | None
    ) -> WebhookResult:
        """Verify a webhook, then grant credits exactly once on confirmation.

        Raises:
            ValueError: unknown provider.
            WebhookVerificationError: signature invalid (-> 400).
        """
        provider = self._factory.get(provider_name)  # ValueError if unknown
        if not provider.verify_signature(raw_body=raw_body, signature_header=signature_header):
            raise WebhookVerificationError("Webhook signature verification failed.")

        event = provider.parse_event(raw_body=raw_body)
        payment = await self._payments.get_by_provider_ref(event.provider_ref)
        if payment is None:
            return WebhookResult(applied=False)  # unknown ref — ignore (idempotent)
        if payment.status == PaymentStatus.CONFIRMED:
            return WebhookResult(applied=False)  # already processed (replay)

        if not event.confirmed:
            return WebhookResult(applied=False)

        payment.status = PaymentStatus.CONFIRMED
        await self._credits.grant(
            payment.org_id,
            payment.credits_granted,
            reason="Credit top-up (payment confirmed)",
            idempotency_key=f"payment:{event.provider_ref}",
        )
        await self._audit.record(
            AuditEvent(
                actor=f"provider:{provider_name}",
                org_id=payment.org_id,
                action="payment.confirmed",
                target=event.provider_ref,
            )
        )
        return WebhookResult(applied=True)
