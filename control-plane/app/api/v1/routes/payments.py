"""Payment + credit routes: checkout, wallet balance, and provider webhooks."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Path, Request
from fastapi import status as http_status

from app.api.v1.dependencies.auth import require_org_role
from app.api.v1.dependencies.services import get_credit_repository, get_payment_service
from app.core.config import PaymentProvider as ProviderName
from app.core.exceptions import NotFoundError
from app.db.models.enums import Role
from app.db.models.user import User
from app.db.repositories.credit_repository import CreditRepository
from app.schemas.common import SuccessResponse
from app.schemas.payment import (
    CheckoutRequest,
    CheckoutResponse,
    WalletView,
    WebhookAck,
)
from app.services.payment_service import PaymentService

router = APIRouter(tags=["payments"])

_VALID_PROVIDERS = {p.value for p in ProviderName}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post(
    "/orgs/{org_id}/credits/checkout",
    response_model=SuccessResponse[CheckoutResponse],
)
async def create_checkout(
    payload: CheckoutRequest,
    request: Request,
    org_id: uuid.UUID = Path(...),
    _user: User = Depends(require_org_role(Role.OWNER, Role.BILLING)),
    service: PaymentService = Depends(get_payment_service),
) -> SuccessResponse[CheckoutResponse]:
    """Start a credit top-up checkout session (OWNER/BILLING only)."""
    result = await service.create_checkout(
        org_id, credits=payload.credits, currency=payload.currency, ip=_client_ip(request)
    )
    p = result.payment
    return SuccessResponse[CheckoutResponse](
        data=CheckoutResponse(
            payment_id=p.id,
            provider=p.provider,
            provider_ref=p.provider_ref,
            checkout_url=result.checkout_url,
            credits=p.credits_granted,
            amount_minor=result.amount_minor,
            currency=p.currency,
        ),
        request_id=_request_id(request),
    )


@router.get("/orgs/{org_id}/credits", response_model=SuccessResponse[WalletView])
async def get_credits(
    request: Request,
    org_id: uuid.UUID = Path(...),
    _user: User = Depends(require_org_role(Role.VIEWER, Role.BILLING, Role.EDITOR, Role.OWNER)),
    credits: CreditRepository = Depends(get_credit_repository),
) -> SuccessResponse[WalletView]:
    """Return the organization's credit wallet balance."""
    wallet = await credits.get_wallet(org_id)
    if wallet is None:
        raise NotFoundError("No credit wallet for this organization.")
    return SuccessResponse[WalletView](
        data=WalletView(balance=wallet.balance, reserved=wallet.reserved),
        request_id=_request_id(request),
    )


@router.post(
    "/webhooks/payments/{provider}",
    response_model=SuccessResponse[WebhookAck],
    status_code=http_status.HTTP_200_OK,
)
async def payment_webhook(
    request: Request,
    provider: str = Path(...),
    service: PaymentService = Depends(get_payment_service),
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    razorpay_signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
) -> SuccessResponse[WebhookAck]:
    """Signature-verified provider webhook. Grants credits only on confirmation."""
    if provider not in _VALID_PROVIDERS:
        raise NotFoundError(f"Unknown payment provider: {provider}")

    raw_body = await request.body()
    signature = stripe_signature if provider == ProviderName.STRIPE.value else razorpay_signature
    result = await service.handle_webhook(
        provider, raw_body=raw_body, signature_header=signature
    )
    return SuccessResponse[WebhookAck](
        data=WebhookAck(received=True, applied=result.applied),
        request_id=_request_id(request),
    )
