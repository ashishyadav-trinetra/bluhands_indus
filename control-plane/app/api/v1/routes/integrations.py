"""Nango integration routes — session tokens, connection list, auth webhook.

Nango is the OAuth/credential layer between BluHands and 800+ external APIs
(Stripe, Shopify, HubSpot, etc.). The flow:
  1. Frontend calls POST /api/v1/integrations/session  → gets a short-lived
     Nango session token scoped to this user + org.
  2. Frontend passes it to Nango's ConnectUI (JS SDK) → OAuth popup.
  3. Nango calls POST /api/v1/integrations/webhook on success → we log the
     connection_id (extend to persist if needed).
  4. Frontend calls GET /api/v1/integrations/connections to list live connections.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Body, Depends, Header, Request
from pydantic import BaseModel

from app.api.v1.dependencies.auth import get_current_user
from app.api.v1.dependencies.providers import get_app_settings
from app.core.config import Settings
from app.core.exceptions import AppError
from app.db.models.user import User
from app.schemas.common import SuccessResponse

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])


class SessionRequest(BaseModel):
    """Request body for creating a Nango connect session."""
    integration_id: str | None = None


def _nango_headers(settings: Settings) -> dict[str, str]:
    if not settings.nango_secret_key:
        raise AppError(
            "Nango is not configured — set FORGE_NANGO_SECRET_KEY",
            code="NANGO_NOT_CONFIGURED",
            http_status=503,
        )
    return {
        "Authorization": f"Bearer {settings.nango_secret_key}",
        "Content-Type": "application/json",
    }


@router.post("/session")
async def create_session(
    body: SessionRequest,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, str]:
    """Return a short-lived Nango session token scoped to this user.

    The frontend passes the returned ``session_token`` to Nango's ConnectUI
    JS SDK, which opens the OAuth modal. Passing ``integration_id`` restricts
    the UI to a single integration (skips the picker).
    """
    payload: dict[str, Any] = {
        "tags": {
            "end_user_id": str(user.id),
            "end_user_email": user.email,
            "end_user_display_name": user.full_name or user.email,
        },
    }
    if body.integration_id:
        payload["allowed_integrations"] = [body.integration_id]

    bound = log.bind(user_id=str(user.id), integration_id=body.integration_id)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.nango_base_url}/connect/sessions",
                headers=_nango_headers(settings),
                json=payload,
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        bound.warning("nango_session_error", status=exc.response.status_code)
        raise AppError(
            "Nango session creation failed",
            code="NANGO_SESSION_ERROR",
            http_status=exc.response.status_code,
        ) from exc
    except httpx.RequestError as exc:
        bound.error("nango_unreachable", error=str(exc))
        raise AppError("Nango is unreachable", code="NANGO_UNAVAILABLE", http_status=502) from exc

    data = resp.json()
    bound.debug("nango_session_created")
    return {"session_token": data["data"]["token"]}


@router.get("/connections")
async def list_connections(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, Any]:
    """List all Nango connections for the authenticated user."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{settings.nango_base_url}/connections",
                headers=_nango_headers(settings),
                params={"tags[end_user_id]": str(user.id)},
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise AppError(
            "Failed to fetch connections from Nango",
            code="NANGO_CONNECTIONS_ERROR",
            http_status=exc.response.status_code,
        ) from exc
    except httpx.RequestError as exc:
        raise AppError("Nango is unreachable", code="NANGO_UNAVAILABLE", http_status=502) from exc

    return resp.json()


class GithubStatus(BaseModel):
    connected: bool


class GithubRepo(BaseModel):
    name: str
    full_name: str
    private: bool
    clone_url: str


@router.get("/github", response_model=SuccessResponse[GithubStatus])
async def github_status(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_app_settings),
) -> SuccessResponse[GithubStatus]:
    """Return whether the authenticated user has a GitHub connection via Nango."""
    if not settings.nango_secret_key:
        return SuccessResponse(data=GithubStatus(connected=False))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.nango_base_url}/connections",
                headers=_nango_headers(settings),
                params={"tags[end_user_id]": str(user.id), "integration_id": "github"},
            )
            resp.raise_for_status()
        connections = resp.json().get("connections", [])
        return SuccessResponse(data=GithubStatus(connected=len(connections) > 0))
    except Exception:
        return SuccessResponse(data=GithubStatus(connected=False))


@router.get("/github/repos", response_model=SuccessResponse[list[GithubRepo]])
async def github_repos(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_app_settings),
) -> SuccessResponse[list[GithubRepo]]:
    """Return the user's accessible GitHub repositories via Nango proxy."""
    if not settings.nango_secret_key:
        return SuccessResponse(data=[])
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            conn_resp = await client.get(
                f"{settings.nango_base_url}/connections",
                headers=_nango_headers(settings),
                params={"tags[end_user_id]": str(user.id), "integration_id": "github"},
            )
            conn_resp.raise_for_status()
            connections = conn_resp.json().get("connections", [])
            if not connections:
                return SuccessResponse(data=[])

            connection_id = connections[0]["id"]
            proxy_resp = await client.get(
                f"{settings.nango_base_url}/proxy/github/user/repos",
                headers={
                    **_nango_headers(settings),
                    "Connection-Id": connection_id,
                    "Provider-Config-Key": "github",
                },
                params={"per_page": 100, "sort": "pushed"},
            )
            proxy_resp.raise_for_status()
            repos = [
                GithubRepo(
                    name=r["name"],
                    full_name=r["full_name"],
                    private=r["private"],
                    clone_url=r["clone_url"],
                )
                for r in proxy_resp.json()
                if isinstance(r, dict)
            ]
            return SuccessResponse(data=repos)
    except Exception:
        return SuccessResponse(data=[])


@router.post("/webhook")
async def nango_webhook(
    request: Request,
    x_nango_signature: str | None = Header(default=None, alias="x-nango-signature"),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, str]:
    """Receive Nango auth webhooks (new connection / reconnect / error).

    Verifies the HMAC-SHA256 signature when ``FORGE_NANGO_WEBHOOK_SECRET`` is set.
    Logs the event; extend here to persist ``connectionId`` to the database.
    """
    body = await request.body()

    if settings.nango_webhook_secret and x_nango_signature:
        expected = hmac.new(
            settings.nango_webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_nango_signature):
            raise AppError("Invalid webhook signature", code="WEBHOOK_SIGNATURE_INVALID", http_status=401)

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}

    log.info(
        "nango_webhook_received",
        event_type=payload.get("type", "unknown"),
        operation=payload.get("operation", ""),
        connection_id=payload.get("connectionId", ""),
        success=payload.get("success", False),
    )

    return {"status": "received"}
