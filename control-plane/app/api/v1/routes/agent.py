"""Proxy routes for agent pre-build steps: clarify and enhance.

Auth required — any logged-in platform user. The control plane forwards the
request to the internal agent service so the frontend never calls the agent
directly (no auth bypass, no URL leakage).
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Body, Depends

from app.api.v1.dependencies.auth import get_current_user
from app.api.v1.dependencies.providers import get_app_settings
from app.core.config import Settings
from app.core.exceptions import AppError
from app.db.models.user import User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


async def _forward(
    agent_url: str,
    path: str,
    payload: dict[str, Any],
    *,
    user_id: str,
) -> dict[str, Any]:
    """Forward *payload* to the agent service at *agent_url + path*.

    Raises:
        AppError (502): agent is unreachable.
        AppError (status from agent): agent returned an error status.
    """
    bound = log.bind(agent_path=path, user_id=user_id)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{agent_url}{path}", json=payload)
            resp.raise_for_status()
            bound.debug("agent_proxy_ok", status=resp.status_code)
            return resp.json()
    except httpx.HTTPStatusError as exc:
        bound.warning("agent_proxy_error", status=exc.response.status_code, detail=exc.response.text)
        raise AppError(
            exc.response.text or "Agent returned an error",
            code="AGENT_ERROR",
            http_status=exc.response.status_code,
        ) from exc
    except httpx.RequestError as exc:
        bound.error("agent_unreachable", error=str(exc))
        raise AppError("Agent service is unreachable", code="AGENT_UNAVAILABLE", http_status=502) from exc


@router.post("/clarify")
async def clarify(
    payload: dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    """Generate clarifying questions for a merchant's build request.

    Proxies to the agent service ``/clarify`` endpoint. The payload is the
    raw merchant input; the agent returns structured questions.
    """
    return await _forward(settings.agent_base_url, "/clarify", payload, user_id=str(user.id))


@router.post("/enhance")
async def enhance(
    payload: dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    """Turn a prompt + clarification answers into a structured build spec.

    Proxies to the agent service ``/enhance`` endpoint. Returns an enhanced
    prompt plus a feature matrix (auth, database, integrations, etc.).
    """
    return await _forward(settings.agent_base_url, "/enhance", payload, user_id=str(user.id))
