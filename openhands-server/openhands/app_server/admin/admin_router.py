"""Admin API routes for managing user model/repo assignments.

Endpoints under /api/v1/admin/assignments, protected by BLUHANDS_ADMIN_EMAILS.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from openhands.app_server.admin.user_assignment_service import (
    UserAssignment,
    get_assignment,
    list_assignments,
    remove_assignment,
    set_assignment,
)
from openhands.app_server.user_auth.supabase_user_auth import _is_platform_admin
from openhands.app_server.user_auth.user_auth import get_user_auth as _get_user_auth

_logger = logging.getLogger(__name__)

router = APIRouter(
    prefix='/admin',
    tags=['Admin'],
)


async def require_admin(request: Request):
    user_auth = await _get_user_auth(request)
    email = await user_auth.get_user_email()
    if not email or not _is_platform_admin(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Admin access required',
        )
    return email


@router.get('/assignments')
async def get_assignments(
    _admin_email: str = Depends(require_admin),
) -> list[dict]:
    return [a.model_dump() for a in list_assignments()]


@router.put('/assignments/{user_id}')
async def upsert_assignment(
    user_id: str,
    body: dict,
    _admin_email: str = Depends(require_admin),
) -> dict:
    assignment = UserAssignment(
        user_id=user_id,
        email=body.get('email', ''),
        model=body['model'],
        base_url=body.get('base_url', ''),
        api_key=body.get('api_key', ''),
        github_token=body.get('github_token', ''),
        assigned_repo=body.get('assigned_repo', ''),
        is_active=body.get('is_active', True),
    )
    try:
        set_assignment(assignment)
        return {'status': 'ok', 'user_id': user_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete('/assignments/{user_id}')
async def delete_assignment(
    user_id: str,
    _admin_email: str = Depends(require_admin),
) -> dict:
    removed = remove_assignment(user_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'No assignment found for user {user_id}',
        )
    return {'status': 'deleted', 'user_id': user_id}
