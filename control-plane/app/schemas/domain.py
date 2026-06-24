"""Domain-related request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DomainAvailabilityResponse(BaseModel):
    """Response for GET /domains/check."""

    domain: str
    available: bool
    price_minor: int = 0
    currency: str = "INR"


class DomainPurchaseRequest(BaseModel):
    """Request body for POST /domains/purchase."""

    domain: str = Field(min_length=3, max_length=253)


class DomainPurchaseResponse(BaseModel):
    ok: bool = True


class EntriSessionRequest(BaseModel):
    """Request body for POST /domains/entri-session."""

    domain: str = Field(min_length=3, max_length=253)


class EntriSessionResponse(BaseModel):
    """Token + app ID needed to call ``entri.showEntri()`` in the browser."""

    token: str
    application_id: str
    dns_records: list[dict]
