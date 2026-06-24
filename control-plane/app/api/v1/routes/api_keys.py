"""Admin API key routes: create (plaintext shown once) / list / revoke."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Path, Request
from fastapi import status as http_status

from app.api.v1.dependencies.auth import require_org_role
from app.api.v1.dependencies.services import get_api_key_service
from app.db.models.enums import Role
from app.db.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyView
from app.schemas.common import SuccessResponse
from app.services.api_key_service import ApiKeyService

router = APIRouter(tags=["api-keys"])


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _view(key) -> ApiKeyView:
    return ApiKeyView(
        id=key.id, name=key.name, prefix=key.prefix,
        rate_limit_per_min=key.rate_limit_per_min,
        last_used_at=key.last_used_at, revoked_at=key.revoked_at,
        created_at=key.created_at,
    )


@router.post(
    "/orgs/{org_id}/api-keys",
    status_code=http_status.HTTP_201_CREATED,
    response_model=SuccessResponse[ApiKeyCreated],
)
async def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    org_id: uuid.UUID = Path(...),
    user: User = Depends(require_org_role(Role.OWNER)),
    service: ApiKeyService = Depends(get_api_key_service),
) -> SuccessResponse[ApiKeyCreated]:
    """Create an API key (OWNER only). The plaintext is returned exactly once."""
    key, plaintext = await service.create_key(
        org_id, name=payload.name, rate_limit_per_min=payload.rate_limit_per_min,
        actor=f"user:{user.id}", ip=_client_ip(request),
    )
    return SuccessResponse[ApiKeyCreated](
        data=ApiKeyCreated(
            id=key.id, name=key.name, prefix=key.prefix,
            api_key=plaintext, rate_limit_per_min=key.rate_limit_per_min,
        ),
        request_id=_request_id(request),
    )


@router.get("/orgs/{org_id}/api-keys", response_model=SuccessResponse[list[ApiKeyView]])
async def list_api_keys(
    request: Request,
    org_id: uuid.UUID = Path(...),
    _user: User = Depends(require_org_role(Role.OWNER)),
    service: ApiKeyService = Depends(get_api_key_service),
) -> SuccessResponse[list[ApiKeyView]]:
    """List the organization's API keys (no secrets)."""
    keys = await service.list_keys(org_id)
    return SuccessResponse[list[ApiKeyView]](
        data=[_view(k) for k in keys], request_id=_request_id(request)
    )


@router.delete(
    "/orgs/{org_id}/api-keys/{key_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
async def revoke_api_key(
    request: Request,
    org_id: uuid.UUID = Path(...),
    key_id: uuid.UUID = Path(...),
    user: User = Depends(require_org_role(Role.OWNER)),
    service: ApiKeyService = Depends(get_api_key_service),
):
    """Revoke an API key (OWNER only)."""
    await service.revoke_key(org_id, key_id, actor=f"user:{user.id}", ip=_client_ip(request))
    from fastapi import Response
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
