"""Payment + credit schemas (Pydantic v2)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    """Request to buy a credit package."""

    credits: int = Field(ge=1, le=1_000_000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class CheckoutResponse(BaseModel):
    """Checkout session details returned to the client."""

    payment_id: uuid.UUID
    provider: str
    provider_ref: str
    checkout_url: str
    credits: int
    amount_minor: int
    currency: str


class WalletView(BaseModel):
    """Current credit wallet balance."""

    balance: int
    reserved: int


class WebhookAck(BaseModel):
    """Webhook acknowledgement (kept minimal — never leak internals)."""

    received: bool = True
    applied: bool = False
