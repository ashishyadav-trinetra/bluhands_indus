"""Shared response envelopes and pagination models.

Every successful response is wrapped in ``SuccessResponse``; every error in
``ErrorResponse``. This keeps the API contract consistent (section 9 of brief).
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class ResponseMeta(BaseModel):
    """Optional metadata (pagination, counts) attached to a response."""

    model_config = ConfigDict(extra="allow")


class PageMeta(ResponseMeta):
    """Cursor/offset pagination metadata."""

    total: int | None = None
    limit: int | None = None
    offset: int | None = None
    next_cursor: str | None = None


class SuccessResponse(BaseModel, Generic[DataT]):
    """Standard success envelope."""

    success: bool = True
    data: DataT
    meta: ResponseMeta | None = None
    request_id: str | None = None


class ErrorBody(BaseModel):
    """Machine + human error detail."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error envelope (never contains stack traces or internals)."""

    success: bool = False
    error: ErrorBody
    request_id: str | None = None


class PaginationParams(BaseModel):
    """Common list query parameters with sane bounds."""

    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
