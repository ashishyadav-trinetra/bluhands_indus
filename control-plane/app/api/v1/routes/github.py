"""GitHub routes (via Nango): connection status + list/create repos.

The OAuth *connect* itself is handled by the existing Nango flow
(``/integrations/session`` + ConnectUI). These endpoints use the resulting Nango
connection to read status and the user's repos. Pushing/pulling the agent's code
happens inside the build sandbox with a token fetched via ``GithubService``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.v1.dependencies.auth import get_current_user
from app.api.v1.dependencies.services import get_github_service
from app.db.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.integrations import GithubStatus, RepoCreate, RepoView
from app.services.github_service import GithubService

router = APIRouter(prefix="/integrations/github", tags=["integrations"])


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@router.get("", response_model=SuccessResponse[GithubStatus])
async def github_status(
    request: Request,
    user: User = Depends(get_current_user),
    service: GithubService = Depends(get_github_service),
) -> SuccessResponse[GithubStatus]:
    """Whether the current user has connected GitHub (via Nango)."""
    status = await service.get_status(user.id)
    return SuccessResponse[GithubStatus](
        data=GithubStatus(connected=status["connected"]),
        request_id=_request_id(request),
    )


@router.get("/repos", response_model=SuccessResponse[list[RepoView]])
async def list_repos(
    request: Request,
    user: User = Depends(get_current_user),
    service: GithubService = Depends(get_github_service),
) -> SuccessResponse[list[RepoView]]:
    """List the connected user's repositories."""
    repos = await service.list_repos(user.id)
    return SuccessResponse[list[RepoView]](
        data=[RepoView(**r) for r in repos], request_id=_request_id(request)
    )


@router.post("/repos", response_model=SuccessResponse[RepoView])
async def create_repo(
    payload: RepoCreate,
    request: Request,
    user: User = Depends(get_current_user),
    service: GithubService = Depends(get_github_service),
) -> SuccessResponse[RepoView]:
    """Create a new repository under the connected account."""
    repo = await service.create_repo(user.id, payload.name, private=payload.private)
    return SuccessResponse[RepoView](data=RepoView(**repo), request_id=_request_id(request))
