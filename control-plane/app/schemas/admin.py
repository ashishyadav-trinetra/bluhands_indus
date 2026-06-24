"""Schemas for the admin panel (user management)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import PlatformRole


class AdminUserView(BaseModel):
    """A user row as shown in the admin panel (no secrets)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None = None
    is_active: bool
    platform_role: str
    created_at: datetime


class AdminOrgView(BaseModel):
    """An organisation row as shown in the admin panel."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class RoleUpdate(BaseModel):
    """Set a user's platform role."""

    platform_role: PlatformRole
