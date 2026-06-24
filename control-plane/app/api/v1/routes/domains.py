"""Domain routes — availability checks and Entri DNS-connect sessions.

These routes are org-agnostic (no org_id path param) since domain search
and purchase happen before tenant creation in the onboarding wizard.

RBAC: any authenticated platform user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.v1.dependencies.auth import get_current_user
from app.api.v1.dependencies.services import get_domain_service
from app.db.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.domain import (
    DomainAvailabilityResponse,
    DomainPurchaseRequest,
    DomainPurchaseResponse,
    EntriSessionRequest,
    EntriSessionResponse,
)
from app.services.domain_service import DomainService

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get(
    "/check",
    response_model=SuccessResponse[DomainAvailabilityResponse],
    summary="Check domain availability",
)
async def check_domain(
    domain: str = Query(..., min_length=3, max_length=253),
    _user: User = Depends(get_current_user),
    service: DomainService = Depends(get_domain_service),
) -> SuccessResponse[DomainAvailabilityResponse]:
    """Proxy to the Entri availability API (stub when no API key is set)."""
    result = await service.check_availability(domain)
    return SuccessResponse(data=DomainAvailabilityResponse(**result))


@router.post(
    "/purchase",
    response_model=SuccessResponse[DomainPurchaseResponse],
    summary="Record a domain purchase intent",
)
async def purchase_domain(
    body: DomainPurchaseRequest,
    _user: User = Depends(get_current_user),
    _service: DomainService = Depends(get_domain_service),
) -> SuccessResponse[DomainPurchaseResponse]:
    """Acknowledge a domain purchase intent.

    The actual checkout is handled by the Entri widget on the client side.
    This endpoint records the intent and returns a success acknowledgement.
    A full implementation would persist the record via ``_service``; that is
    intentionally deferred until payment persistence is wired.
    """
    # NOTE: body.domain is available here for future persistence via _service.
    # Until then, we return 200 so the frontend wizard can proceed.
    return SuccessResponse(data=DomainPurchaseResponse())


@router.post(
    "/entri-session",
    response_model=SuccessResponse[EntriSessionResponse],
    summary="Create an Entri DNS-connect session for the BYO widget",
)
async def create_entri_session(
    body: EntriSessionRequest,
    _user: User = Depends(get_current_user),
    service: DomainService = Depends(get_domain_service),
) -> SuccessResponse[EntriSessionResponse]:
    """Generate a short-lived Entri session token for the DNS-connect widget.

    The browser passes ``token`` and ``applicationId`` to ``entri.showEntri()``
    which guides the user through DNS configuration at their registrar.
    """
    token = await service.create_session(body.domain)
    dns_records = service.platform_dns_records(body.domain)
    return SuccessResponse(data=EntriSessionResponse(
        token=token,
        application_id=service.app_id,
        dns_records=dns_records,
    ))
