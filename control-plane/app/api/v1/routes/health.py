"""Health and readiness probes.

- ``/health``      : liveness (no dependencies checked).
- ``/health/live`` : always-200 liveness probe (K8s livenessProbe).
- ``/health/ready``: 200 only if DB + Redis (+ storage if configured) are reachable.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.session import get_db_session
from app.providers.redis_client import get_redis
from app.schemas.health import DependencyStatus, LivenessResponse, ReadinessResponse

router = APIRouter()
_logger = get_logger("health")


@router.get("/health", response_model=LivenessResponse)
async def health() -> LivenessResponse:
    """Liveness: the process is up. No dependencies are checked."""
    return LivenessResponse(version=__version__)


@router.get("/health/live", response_model=LivenessResponse)
async def live() -> LivenessResponse:
    """Always-200 liveness probe for orchestrators."""
    return LivenessResponse(version=__version__)


async def _check_database(session: AsyncSession) -> DependencyStatus:
    try:
        await session.execute(text("SELECT 1"))
        return DependencyStatus(name="database", healthy=True)
    except Exception as exc:  # noqa: BLE001 - report, never expose internals
        _logger.error("readiness_db_failed", error=str(exc))
        return DependencyStatus(name="database", healthy=False, detail="unreachable")


async def _check_redis(redis: Redis) -> DependencyStatus:
    try:
        await redis.ping()
        return DependencyStatus(name="redis", healthy=True)
    except Exception as exc:  # noqa: BLE001
        _logger.error("readiness_redis_failed", error=str(exc))
        return DependencyStatus(name="redis", healthy=False, detail="unreachable")


async def _check_storage(settings: Settings) -> DependencyStatus:
    if not settings.s3_endpoint_url:
        return DependencyStatus(name="storage", healthy=True, detail="not_configured")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            # Any HTTP response means the endpoint is reachable.
            await client.get(settings.s3_endpoint_url)
        return DependencyStatus(name="storage", healthy=True)
    except Exception as exc:  # noqa: BLE001
        _logger.error("readiness_storage_failed", error=str(exc))
        return DependencyStatus(name="storage", healthy=False, detail="unreachable")


@router.get("/health/ready", response_model=ReadinessResponse)
async def ready(
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> ReadinessResponse:
    """Readiness: returns 503 unless all critical dependencies are reachable."""
    deps = [
        await _check_database(session),
        await _check_redis(redis),
        await _check_storage(settings),
    ]
    all_healthy = all(d.healthy for d in deps)
    response.status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ready" if all_healthy else "not_ready", dependencies=deps)
