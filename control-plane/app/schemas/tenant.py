"""Tenant request / response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import Industry, IsolationLevel, TenantStatus


class TenantCreate(BaseModel):
    """Request body for creating a new tenant."""

    industry: Industry
    isolation_level: IsolationLevel = IsolationLevel.POOLED
    display_name: str | None = Field(default=None, max_length=200)
    region: str = Field(default="us-east-1", max_length=40)


class TenantResponse(BaseModel):
    """Tenant representation returned to callers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    industry: Industry
    isolation_level: IsolationLevel
    status: TenantStatus
    display_name: str | None
    region: str
    created_at: datetime
    updated_at: datetime
