"""API key schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    """Request to create a named API key."""

    name: str = Field(min_length=1, max_length=120)
    rate_limit_per_min: int = Field(default=100, ge=1, le=10_000)


class ApiKeyCreated(BaseModel):
    """Returned exactly once at creation — contains the plaintext key."""

    id: uuid.UUID
    name: str
    prefix: str
    api_key: str  # plaintext — shown once, never stored
    rate_limit_per_min: int


class ApiKeyView(BaseModel):
    """Safe view of an API key (no secret)."""

    id: uuid.UUID
    name: str
    prefix: str
    rate_limit_per_min: int
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
