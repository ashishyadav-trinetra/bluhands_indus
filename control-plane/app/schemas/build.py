"""Pydantic schemas for BuildRun request/response."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import BuildStatus


class BuildStartRequest(BaseModel):
    """Body for POST /orgs/{org_id}/tenants/{tenant_id}/builds."""

    prompt: str = Field(..., min_length=10, max_length=8000,
                        description="Natural-language description of the app to build.")
    idempotency_key: str | None = Field(
        default=None,
        max_length=128,
        description="Client-supplied key; re-submitting the same key returns the "
                    "existing build rather than creating a duplicate.",
    )
    custom_domain: str | None = Field(
        default=None,
        max_length=253,
        description="Domain chosen during onboarding; saved on the tenant row.",
    )
    # GitHub (user-driven, optional). Token is fetched from Nango at run time.
    github_repo_url: str | None = Field(default=None, max_length=500)
    github_branch: str | None = Field(default=None, max_length=200)
    github_push: bool = False
    github_pull: bool = False


class BuildRunResponse(BaseModel):
    """Public representation of a BuildRun row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    status: BuildStatus
    prompt: str | None
    celery_task_id: str | None
    credits_cost: int
    preview_url: str | None
    prod_url: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
