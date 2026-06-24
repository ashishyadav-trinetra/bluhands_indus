"""Tenant routes — org-scoped CRUD under /api/v1/orgs/{org_id}/tenants."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Path, Query, Request, status

from app.api.v1.dependencies.auth import require_org_role
from app.api.v1.dependencies.services import get_tenant_service
from app.db.models.enums import Role
from app.db.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.tenant import TenantCreate, TenantResponse
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/orgs/{org_id}/tenants", tags=["tenants"])

_ANY_ORG_MEMBER = (Role.OWNER, Role.EDITOR, Role.VIEWER, Role.BILLING)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[TenantResponse],
    summary="Create a tenant for an organisation",
)
async def create_tenant(
    request: Request,
    body: TenantCreate,
    org_id: uuid.UUID = Path(...),
    user: User = Depends(require_org_role(Role.OWNER, Role.EDITOR)),
    service: TenantService = Depends(get_tenant_service),
) -> SuccessResponse[TenantResponse]:
    tenant = await service.create_tenant(
        org_id,
        body,
        actor=f"user:{user.id}",
        ip=_client_ip(request),
    )
    return SuccessResponse(data=TenantResponse.model_validate(tenant))


@router.get(
    "",
    response_model=SuccessResponse[list[TenantResponse]],
    summary="List tenants for an organisation",
)
async def list_tenants(
    org_id: uuid.UUID = Path(...),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _user: User = Depends(require_org_role(*_ANY_ORG_MEMBER)),
    service: TenantService = Depends(get_tenant_service),
) -> SuccessResponse[list[TenantResponse]]:
    tenants = await service.list_tenants(org_id, skip=skip, limit=limit)
    return SuccessResponse(data=[TenantResponse.model_validate(t) for t in tenants])


@router.get(
    "/{tenant_id}",
    response_model=SuccessResponse[TenantResponse],
    summary="Get a single tenant",
)
async def get_tenant(
    org_id: uuid.UUID = Path(...),
    tenant_id: uuid.UUID = Path(...),
    _user: User = Depends(require_org_role(*_ANY_ORG_MEMBER)),
    service: TenantService = Depends(get_tenant_service),
) -> SuccessResponse[TenantResponse]:
    tenant = await service.get_tenant(tenant_id, org_id=org_id)
    return SuccessResponse(data=TenantResponse.model_validate(tenant))
