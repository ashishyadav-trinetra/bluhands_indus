"""Build routes — tenant-scoped under /api/v1/orgs/{org_id}/tenants/{tenant_id}/builds.

RBAC:
  - POST   (start build)   → OWNER, EDITOR
  - GET    (list/status)   → any org member
  - POST   /approve        → OWNER only  + X-Confirm-Action: true
  - POST   /cancel         → OWNER, EDITOR
  - DELETE /{build_id}     → OWNER only
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Path, Query, Request, status
from fastapi.responses import Response

from app.api.v1.dependencies.auth import require_org_role
from app.api.v1.dependencies.providers import get_app_settings
from app.api.v1.dependencies.services import get_build_service
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.db.models.enums import Role
from app.db.models.user import User
from app.schemas.build import BuildRunResponse, BuildStartRequest
from app.schemas.common import PageMeta, SuccessResponse
from app.services.build_service import BuildService

router = APIRouter(
    prefix="/orgs/{org_id}/tenants/{tenant_id}/builds",
    tags=["builds"],
)

_ANY_ORG_MEMBER = (Role.OWNER, Role.EDITOR, Role.VIEWER, Role.BILLING)
_CONFIRM_HEADER = "X-Confirm-Action"


def _client_ip(request: Request) -> str | None:
    """Extract best-effort client IP from forwarded headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SuccessResponse[BuildRunResponse],
    summary="Start a new build for a tenant",
)
async def start_build(
    request: Request,
    body: BuildStartRequest,
    org_id: uuid.UUID = Path(...),
    tenant_id: uuid.UUID = Path(...),
    user: User = Depends(require_org_role(Role.OWNER, Role.EDITOR)),
    service: BuildService = Depends(get_build_service),
    settings: Settings = Depends(get_app_settings),
) -> SuccessResponse[BuildRunResponse]:
    """Enqueue a new build job and return 202 Accepted with the build ID.

    The LLM the agent uses is chosen from the requester's platform role
    (tester/self get fixed models) and persisted on the build run.
    """
    build_run = await service.start_build(
        tenant_id, org_id, body,
        actor=f"user:{user.id}",
        ip=_client_ip(request),
        llm_model=settings.model_for_role(user.platform_role),
    )
    return SuccessResponse(data=BuildRunResponse.model_validate(build_run))


@router.get(
    "",
    response_model=SuccessResponse[list[BuildRunResponse]],
    summary="List builds for a tenant",
)
async def list_builds(
    org_id: uuid.UUID = Path(...),
    tenant_id: uuid.UUID = Path(...),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _user: User = Depends(require_org_role(*_ANY_ORG_MEMBER)),
    service: BuildService = Depends(get_build_service),
) -> SuccessResponse[list[BuildRunResponse]]:
    """Return a paginated list of build runs for the given tenant."""
    builds = await service.list_builds(tenant_id, org_id, skip=skip, limit=limit)
    return SuccessResponse(
        data=[BuildRunResponse.model_validate(b) for b in builds],
        meta=PageMeta(offset=skip, limit=limit),
    )


@router.get(
    "/{build_id}",
    response_model=SuccessResponse[BuildRunResponse],
    summary="Get build run status",
)
async def get_build(
    org_id: uuid.UUID = Path(...),
    tenant_id: uuid.UUID = Path(...),
    build_id: uuid.UUID = Path(...),
    _user: User = Depends(require_org_role(*_ANY_ORG_MEMBER)),
    service: BuildService = Depends(get_build_service),
) -> SuccessResponse[BuildRunResponse]:
    """Return the current status and metadata for a single build run."""
    build_run = await service.get_build(build_id, tenant_id=tenant_id)
    return SuccessResponse(data=BuildRunResponse.model_validate(build_run))


@router.post(
    "/{build_id}/approve",
    response_model=SuccessResponse[BuildRunResponse],
    summary="Approve a build in REVIEW state (owner only)",
)
async def approve_build(
    request: Request,
    org_id: uuid.UUID = Path(...),
    tenant_id: uuid.UUID = Path(...),
    build_id: uuid.UUID = Path(...),
    x_confirm_action: str | None = Header(default=None, alias=_CONFIRM_HEADER),
    user: User = Depends(require_org_role(Role.OWNER)),
    service: BuildService = Depends(get_build_service),
) -> SuccessResponse[BuildRunResponse]:
    """Approve a REVIEW build, transitioning it to LIVE.

    Requires the ``X-Confirm-Action: true`` header as an extra safeguard
    against accidental approval from automated clients.
    """
    if x_confirm_action != "true":
        raise AuthorizationError(
            f"Destructive action requires header '{_CONFIRM_HEADER}: true'"
        )
    build_run = await service.approve_build(
        build_id, tenant_id, org_id,
        actor=f"user:{user.id}",
        ip=_client_ip(request),
    )
    return SuccessResponse(data=BuildRunResponse.model_validate(build_run))


@router.post(
    "/{build_id}/cancel",
    response_model=SuccessResponse[BuildRunResponse],
    summary="Cancel an in-progress build",
)
async def cancel_build(
    request: Request,
    org_id: uuid.UUID = Path(...),
    tenant_id: uuid.UUID = Path(...),
    build_id: uuid.UUID = Path(...),
    user: User = Depends(require_org_role(Role.OWNER, Role.EDITOR)),
    service: BuildService = Depends(get_build_service),
) -> SuccessResponse[BuildRunResponse]:
    """Cancel a build that has not yet reached a terminal state."""
    build_run = await service.cancel_build(
        build_id, tenant_id, org_id,
        actor=f"user:{user.id}",
        ip=_client_ip(request),
    )
    return SuccessResponse(data=BuildRunResponse.model_validate(build_run))


@router.delete(
    "/{build_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a build (owner only)",
)
async def delete_build(
    request: Request,
    org_id: uuid.UUID = Path(...),
    tenant_id: uuid.UUID = Path(...),
    build_id: uuid.UUID = Path(...),
    user: User = Depends(require_org_role(Role.OWNER)),
    service: BuildService = Depends(get_build_service),
) -> None:
    """Hard-delete a build record.  Cancels it first if still running."""
    await service.delete_build(
        build_id, tenant_id, org_id,
        actor=f"user:{user.id}",
        ip=_client_ip(request),
    )
