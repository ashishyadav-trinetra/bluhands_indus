"""Admin panel routes: list users, list orgs, change a user's platform role.

Platform-admin only (RBAC: ``require_platform_admin``). All database access
goes through AdminService — no direct repository calls in this module.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Path, Query, Request

from app.api.v1.dependencies.auth import require_platform_admin
from app.api.v1.dependencies.services import get_admin_service
from app.db.models.user import User
from app.schemas.admin import AdminOrgView, AdminUserView, RoleUpdate
from app.schemas.common import SuccessResponse
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("/stats")
async def get_stats(
    request: Request,
    _admin: User = Depends(require_platform_admin),
    service: AdminService = Depends(get_admin_service),
) -> SuccessResponse[dict]:
    """Platform-wide summary stats (admin only)."""
    users = await service.list_users(limit=10000, offset=0)
    orgs = await service.list_orgs(limit=10000, offset=0)
    return SuccessResponse[dict](
        data={
            "total_users": len(users),
            "total_orgs": len(orgs),
            "paid_orgs": 0,
            "free_orgs": len(orgs),
            "pro_orgs": 0,
            "business_orgs": 0,
        },
        request_id=_request_id(request),
    )


@router.get("/users", response_model=SuccessResponse[list[AdminUserView]])
async def list_users(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_platform_admin),
    service: AdminService = Depends(get_admin_service),
) -> SuccessResponse[list[AdminUserView]]:
    """List platform users (admin only)."""
    users = await service.list_users(limit=limit, offset=offset)
    return SuccessResponse[list[AdminUserView]](
        data=[AdminUserView.model_validate(u) for u in users],
        request_id=_request_id(request),
    )


@router.patch("/users/{user_id}/role", response_model=SuccessResponse[AdminUserView])
async def set_user_role(
    payload: RoleUpdate,
    request: Request,
    user_id: uuid.UUID = Path(...),
    admin: User = Depends(require_platform_admin),
    service: AdminService = Depends(get_admin_service),
) -> SuccessResponse[AdminUserView]:
    """Change a user's platform role (user / admin / tester / self)."""
    updated = await service.set_role(
        user_id,
        payload.platform_role,
        actor=f"user:{admin.id}",
        ip=_client_ip(request),
    )
    return SuccessResponse[AdminUserView](
        data=AdminUserView.model_validate(updated),
        request_id=_request_id(request),
    )


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    request: Request,
    user_id: uuid.UUID = Path(...),
    admin: User = Depends(require_platform_admin),
    service: AdminService = Depends(get_admin_service),
):
    """Soft-delete a user (admin only; cannot delete yourself)."""
    from fastapi import Response

    await service.delete_user(
        user_id,
        acting_user_id=admin.id,
        actor=f"user:{admin.id}",
        ip=_client_ip(request),
    )
    return Response(status_code=204)


@router.get("/orgs", response_model=SuccessResponse[list[AdminOrgView]])
async def list_orgs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_platform_admin),
    service: AdminService = Depends(get_admin_service),
) -> SuccessResponse[list[AdminOrgView]]:
    """List all organisations (admin only)."""
    orgs = await service.list_orgs(limit=limit, offset=offset)
    return SuccessResponse[list[AdminOrgView]](
        data=[AdminOrgView.model_validate(o) for o in orgs],
        request_id=_request_id(request),
    )
