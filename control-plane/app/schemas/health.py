"""Health-check response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    """Liveness probe payload."""

    status: str = "ok"
    version: str


class DependencyStatus(BaseModel):
    """Status of a single downstream dependency."""

    name: str
    healthy: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    """Readiness probe payload aggregating dependency checks."""

    status: str
    dependencies: list[DependencyStatus]
