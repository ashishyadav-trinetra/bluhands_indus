"""Auth request/response schemas (Pydantic v2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload to create a new user + their first organization."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)
    organization_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    """Email + password login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Access token payload. The refresh token is set as an HttpOnly cookie."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MembershipView(BaseModel):
    """A user's role in one organization."""

    org_id: uuid.UUID
    organization_name: str
    role: str


class UserView(BaseModel):
    """Public view of a user."""

    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    is_platform_admin: bool
    created_at: datetime


class MeResponse(BaseModel):
    """Current user profile plus memberships."""

    user: UserView
    memberships: list[MembershipView]
