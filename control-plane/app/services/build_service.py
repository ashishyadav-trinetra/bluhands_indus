"""BuildService — orchestrates build run lifecycle.

Patterns applied:
- Service Layer (§5.2): all business logic lives here, not in routes.
- DIP (§5.1): depends on ``*Protocol`` abstractions injected via FastAPI ``Depends()``.
- Repository (§5.2): no raw SQL here — all persistence through repos.

Phase 4: CreditService wired — reserve on start, capture on approve.
Refund on failure lives in the Celery task (build_tasks.py) since that is
the component that learns of failure first.
"""

from __future__ import annotations

import uuid

from app.core.exceptions import NotFoundError
from app.db.models.audit import AuditEvent
from app.db.models.build_run import BuildRun
from app.db.models.enums import BuildStatus
from app.schemas.build import BuildStartRequest
from app.services.protocols import (
    AuditLoggerProtocol,
    BuildDispatcherProtocol,
    BuildRunRepositoryProtocol,
    CreditServiceProtocol,
    TenantRepositoryProtocol,
)

_DEFAULT_QUEUE: str = "default"


class BuildService:
    """Business logic for build orchestration.

    Args:
        builds:            Repository for BuildRun persistence.
        tenants:           Repository for tenant reads (ownership validation).
        dispatcher:        Celery task enqueuer.
        credits:           Credit ledger service (reserve/capture/refund).
        audit:             Append-only audit log sink.
        build_credit_cost: Credits deducted per build (from settings).
    """

    def __init__(
        self,
        *,
        builds: BuildRunRepositoryProtocol,
        tenants: TenantRepositoryProtocol,
        dispatcher: BuildDispatcherProtocol,
        credits: CreditServiceProtocol,
        audit: AuditLoggerProtocol,
        build_credit_cost: int = 10,
    ) -> None:
        self._builds = builds
        self._tenants = tenants
        self._dispatcher = dispatcher
        self._credits = credits
        self._audit = audit
        self._build_credit_cost = build_credit_cost

    async def start_build(
        self,
        tenant_id: uuid.UUID,
        org_id: uuid.UUID,
        data: BuildStartRequest,
        *,
        actor: str,
        ip: str | None = None,
        llm_model: str | None = None,
        started_by: uuid.UUID | None = None,
    ) -> BuildRun:
        """Create a QUEUED BuildRun and enqueue the Celery task.

        Steps:
          1. Verify tenant exists and belongs to the caller's org.
          2. Persist ``BuildRun(status=QUEUED, credits_cost=...)``.
          3. Reserve credits (raises InsufficientCreditsError if balance low).
          4. Enqueue ``build.run_build`` with deterministic ``task_id``.
          5. Patch ``celery_task_id`` onto the row.
          6. Emit ``build.started`` audit event.

        Raises:
            NotFoundError:            if tenant not found or org mismatch.
            InsufficientCreditsError: if org wallet balance < build_credit_cost.
        """
        tenant = await self._tenants.get_by_id(tenant_id)
        if tenant is None or tenant.org_id != org_id:
            raise NotFoundError("Tenant not found")

        if data.custom_domain:
            tenant.custom_domain = data.custom_domain

        build_run = BuildRun(
            tenant_id=tenant_id,
            status=BuildStatus.QUEUED,
            prompt=data.prompt,
            llm_model=llm_model,
            started_by=started_by,
            github_repo_url=data.github_repo_url,
            github_branch=data.github_branch,
            github_push=data.github_push,
            github_pull=data.github_pull,
            credits_cost=self._build_credit_cost,
        )
        build_run = await self._builds.create(build_run)

        # Reserve credits after persisting so we have a build_run_id for the
        # idempotency key. If reserve raises the transaction rolls back and
        # the build row never commits; Celery is not dispatched.
        await self._credits.reserve(
            org_id,
            self._build_credit_cost,
            build_run_id=build_run.id,
            idempotency_key=f"reserve:{build_run.id}",
        )

        task_id = self._dispatcher.dispatch(build_run.id, queue=_DEFAULT_QUEUE)
        build_run.celery_task_id = task_id

        await self._audit.record(AuditEvent(
            actor=actor,
            org_id=org_id,
            tenant_id=tenant_id,
            action="build.started",
            target=str(build_run.id),
            ip=ip,
        ))
        return build_run

    async def get_build(
        self,
        build_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
    ) -> BuildRun:
        """Return a BuildRun scoped to a tenant.

        Raises:
            NotFoundError: if build does not exist or belongs to a different tenant.
        """
        build_run = await self._builds.get_by_id(build_id)
        if build_run is None or build_run.tenant_id != tenant_id:
            raise NotFoundError("Build not found")
        return build_run

    async def list_builds(
        self,
        tenant_id: uuid.UUID,
        org_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[BuildRun]:
        """Return paginated BuildRuns for a tenant.

        Raises:
            NotFoundError: if tenant not found or org mismatch.
        """
        tenant = await self._tenants.get_by_id(tenant_id)
        if tenant is None or tenant.org_id != org_id:
            raise NotFoundError("Tenant not found")
        return await self._builds.list_for_tenant(tenant_id, skip=skip, limit=limit)

    async def cancel_build(
        self,
        build_id: uuid.UUID,
        tenant_id: uuid.UUID,
        org_id: uuid.UUID,
        *,
        actor: str,
        ip: str | None = None,
    ) -> BuildRun:
        """Cancel a build that has not reached a terminal state.

        Raises:
            NotFoundError:   if build or tenant not found / org mismatch.
            ValidationError: if build is already in a terminal state.
        """
        from app.core.exceptions import ValidationError

        _TERMINAL = {BuildStatus.LIVE, BuildStatus.FAILED, BuildStatus.CANCELLED}

        build_run = await self.get_build(build_id, tenant_id=tenant_id)
        tenant = await self._tenants.get_by_id(tenant_id)
        if tenant is None or tenant.org_id != org_id:
            raise NotFoundError("Tenant not found")

        if build_run.status in _TERMINAL:
            raise ValidationError(
                f"Build is already in terminal state '{build_run.status.value}'"
            )

        build_run = await self._builds.transition(
            build_run, to_status=BuildStatus.CANCELLED
        )
        await self._audit.record(AuditEvent(
            actor=actor,
            org_id=org_id,
            tenant_id=tenant_id,
            action="build.cancelled",
            target=str(build_run.id),
            ip=ip,
        ))
        return build_run

    async def delete_build(
        self,
        build_id: uuid.UUID,
        tenant_id: uuid.UUID,
        org_id: uuid.UUID,
        *,
        actor: str,
        ip: str | None = None,
    ) -> None:
        """Hard-delete a BuildRun after cancelling it if still running.

        Steps:
          1. Verify ownership (tenant + org).
          2. Cancel if non-terminal (releases the agent sandbox).
          3. Refund reserved credits that were never captured.
          4. Hard-delete the database row.
          5. Emit ``build.deleted`` audit event.

        Raises:
            NotFoundError: if build or tenant not found / org mismatch.
        """
        _TERMINAL = {BuildStatus.LIVE, BuildStatus.FAILED, BuildStatus.CANCELLED}

        build_run = await self.get_build(build_id, tenant_id=tenant_id)
        tenant = await self._tenants.get_by_id(tenant_id)
        if tenant is None or tenant.org_id != org_id:
            raise NotFoundError("Tenant not found")

        # Cancel non-terminal builds so the agent sandbox is released.
        if build_run.status not in _TERMINAL:
            try:
                build_run = await self._builds.transition(
                    build_run, to_status=BuildStatus.CANCELLED
                )
            except Exception:  # noqa: BLE001 - proceed to delete even if transition fails
                pass

        # Refund credits reserved for cancelled builds (QUEUED/RUNNING → CANCELLED).
        if build_run.status == BuildStatus.CANCELLED and build_run.credits_cost:
            try:
                await self._credits.refund(
                    org_id,
                    build_run_id=build_run.id,
                    idempotency_key=f"refund-delete:{build_run.id}",
                )
            except Exception:  # noqa: BLE001 - best-effort; don't block delete
                pass

        await self._builds.delete(build_run)

        await self._audit.record(AuditEvent(
            actor=actor,
            org_id=org_id,
            tenant_id=tenant_id,
            action="build.deleted",
            target=str(build_id),
            ip=ip,
        ))

    async def approve_build(
        self,
        build_id: uuid.UUID,
        tenant_id: uuid.UUID,
        org_id: uuid.UUID,
        *,
        actor: str,
        ip: str | None = None,
    ) -> BuildRun:
        """Approve a REVIEW build → LIVE and capture the reserved credits.

        Raises:
            NotFoundError:   if build or tenant not found / org mismatch.
            ValidationError: if build is not in REVIEW state.
        """
        from app.core.exceptions import ValidationError

        build_run = await self.get_build(build_id, tenant_id=tenant_id)
        tenant = await self._tenants.get_by_id(tenant_id)
        if tenant is None or tenant.org_id != org_id:
            raise NotFoundError("Tenant not found")

        if build_run.status != BuildStatus.REVIEW:
            raise ValidationError(
                f"Build must be in REVIEW state to approve; current: '{build_run.status.value}'"
            )

        await self._credits.capture(
            org_id,
            build_run_id=build_run.id,
            idempotency_key=f"capture:{build_run.id}",
        )

        build_run = await self._builds.transition(
            build_run, to_status=BuildStatus.LIVE
        )
        await self._audit.record(AuditEvent(
            actor=actor,
            org_id=org_id,
            tenant_id=tenant_id,
            action="build.approved",
            target=str(build_run.id),
            ip=ip,
        ))
        return build_run
