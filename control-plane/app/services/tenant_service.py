"""Tenant management business logic.

Single responsibility: create / retrieve / list tenants for an organisation.
Enforces ADR-7 (isolation policy per plan) and the one-tenant-per-industry
constraint. Depends on repository protocols so it is fully unit-testable
with in-memory fakes.
"""

from __future__ import annotations

import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.audit import AuditEvent
from app.db.models.enums import TenantStatus
from app.db.models.tenant import Tenant
from app.schemas.tenant import TenantCreate
from app.services.protocols import AuditLoggerProtocol, TenantRepositoryProtocol


class TenantService:
    """Coordinates tenant lifecycle operations."""

    def __init__(
        self,
        *,
        tenants: TenantRepositoryProtocol,
        audit: AuditLoggerProtocol,
    ) -> None:
        self._tenants = tenants
        self._audit = audit

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_tenant(
        self,
        org_id: uuid.UUID,
        data: TenantCreate,
        *,
        actor: str,
        ip: str | None = None,
    ) -> Tenant:
        """Create a tenant for ``org_id`` with the requested industry.

        Enforces the one-active-tenant-per-industry-per-org constraint
        (ADR-7: isolation level is a policy field on the tenant row).

        Args:
            org_id: The organisation that owns this tenant.
            data: Validated creation payload (industry, isolation, region, …).
            actor: Principal string for the audit log (``"user:<uuid>"``).
            ip: Caller IP, forwarded to the audit record.

        Returns:
            The newly created Tenant.

        Raises:
            ConflictError: If a non-deleted tenant for the same industry already
                exists within this organisation.
        """
        existing = await self._tenants.get_by_org_and_industry(org_id, data.industry)
        if existing is not None:
            raise ConflictError(
                f"A tenant for industry '{data.industry.value}' already exists "
                "in this organisation"
            )

        tenant = Tenant(
            org_id=org_id,
            industry=data.industry,
            isolation_level=data.isolation_level,
            display_name=data.display_name,
            region=data.region,
            status=TenantStatus.CREATED,
        )
        tenant = await self._tenants.create(tenant)

        await self._audit.record(
            AuditEvent(
                actor=actor,
                org_id=org_id,
                tenant_id=tenant.id,
                action="tenant.created",
                target=str(tenant.id),
                ip=ip,
            )
        )
        return tenant

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        org_id: uuid.UUID,
    ) -> Tenant:
        """Return a tenant by id, verifying it belongs to ``org_id``.

        Returning the same NotFoundError for both "doesn't exist" and "wrong org"
        prevents org-id enumeration.

        Raises:
            NotFoundError: If the tenant is absent or owned by a different org.
        """
        tenant = await self._tenants.get_by_id(tenant_id)
        if tenant is None or tenant.org_id != org_id:
            raise NotFoundError("Tenant not found")
        return tenant

    async def list_tenants(
        self,
        org_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Tenant]:
        """Return a page of tenants belonging to ``org_id``."""
        return await self._tenants.list_for_org(org_id, skip=skip, limit=limit)
