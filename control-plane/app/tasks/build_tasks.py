"""Celery build task.

The task body is thin: it wires real dependencies and delegates all FSM
logic to ``BuildTaskExecutor``, which is fully testable offline.

Retry strategy: exponential backoff (10 * 2^attempt seconds), max 5 retries.
After exhaustion the task is routed to the dead-letter queue (build.dlq) via
the on_failure hook so ops can inspect and manually re-drive if needed.

Credit refund: on FAILED (either via retry exhaustion or soft timeout) the
credit reserve is refunded via CreditService. Refund is idempotent — safe
to call multiple times with the same idempotency key.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_SOFT_LIMIT = 1500   # 25 min — raise SoftTimeLimitExceeded
_HARD_LIMIT = 1800   # 30 min — SIGKILL


@celery_app.task(
    name="build.run_build",
    bind=True,
    queue="default",
    acks_late=True,
    max_retries=5,
    soft_time_limit=_SOFT_LIMIT,
    time_limit=_HARD_LIMIT,
)
def run_build(self: Task, build_id: str) -> dict:
    """Execute one build job.

    Receives only the ``build_id`` string; all state is loaded from the DB
    inside the task to prevent stale or injected broker payloads.
    """
    logger.info("build task started", extra={"build_id": build_id, "task_id": self.request.id})
    try:
        asyncio.run(_execute(build_id))
        from app.core.metrics import inc_build_terminal, inc_celery_task
        inc_celery_task('build.run_build', 'success')
        inc_build_terminal('review')
    except SoftTimeLimitExceeded:
        # Soft limit hit — mark FAILED and refund credits; do not retry.
        logger.error("build task soft time limit exceeded", extra={"build_id": build_id})
        asyncio.run(_force_fail_and_refund(build_id, error="Task exceeded soft time limit"))
        from app.core.metrics import inc_build_terminal, inc_celery_task
        inc_celery_task("build.run_build", "failure")
        inc_build_terminal("failed")
        return {"build_id": build_id, "status": "failed", "reason": "timeout"}
    except Exception as exc:
        from app.core.metrics import inc_build_terminal, inc_celery_task
        if self.request.retries >= self.max_retries:
            # Final retry exhausted — refund before giving up.
            asyncio.run(_refund_credits(build_id))
            inc_celery_task('build.run_build', 'failure')
            inc_build_terminal('failed')
        else:
            inc_celery_task('build.run_build', 'retry')
        backoff = 10 * (2 ** self.request.retries)
        logger.warning(
            "build task failed, retrying",
            extra={"build_id": build_id, "attempt": self.request.retries, "backoff": backoff},
        )
        raise self.retry(exc=exc, countdown=backoff)  # noqa: B904 (Celery Retry)

    return {"build_id": build_id, "status": "review_ready"}


async def _execute(build_id: str) -> None:
    """Wire real dependencies and run the executor."""
    from app.core.config import get_settings
    from app.db.repositories.audit_repository import AuditRepository
    from app.db.repositories.backend_repository import BackendRepository
    from app.db.repositories.build_run_repository import BuildRunRepository
    from app.db.repositories.tenant_repository import TenantRepository
    from app.db.task_session import task_session
    from app.tasks.agent_client import get_agent_client
    from app.tasks.build_executor import BuildTaskExecutor

    settings = get_settings()

    async def _github_token(user_id):
        from app.services.github_service import GithubService

        try:
            return await GithubService(settings=settings).get_token(user_id)
        except Exception:  # noqa: BLE001 - missing/failed GitHub token must not fail the build
            return None

    async with task_session() as session:
        executor = BuildTaskExecutor(
            builds=BuildRunRepository(session),
            tenants=TenantRepository(session),
            agent=get_agent_client(settings),
            audit=AuditRepository(session),
            backends=BackendRepository(session),
            github_token_resolver=_github_token,
        )
        await executor.execute(build_id)


async def _force_fail_and_refund(build_id: str, *, error: str) -> None:
    """Best-effort FAILED transition + credit refund (used on soft timeout)."""
    try:
        from app.db.models.enums import BuildStatus
        from app.db.repositories.build_run_repository import BuildRunRepository
        from app.db.repositories.credit_repository import CreditRepository
        from app.db.task_session import task_session
        from app.services.credit_service import CreditService

        async with task_session() as session:
            repo = BuildRunRepository(session)
            build_run = await repo.get_by_id(uuid.UUID(build_id))
            if build_run is None:
                return
            if build_run.status not in {BuildStatus.FAILED, BuildStatus.CANCELLED}:
                await repo.transition(build_run, to_status=BuildStatus.FAILED, error=error)

            # Resolve org_id via the tenant relationship (tenant carries org_id).
            from app.db.repositories.tenant_repository import TenantRepository
            tenant = await TenantRepository(session).get_by_id(build_run.tenant_id)
            if tenant is not None:
                credit_svc = CreditService(credits=CreditRepository(session))
                await credit_svc.refund(
                    tenant.org_id,
                    build_run_id=build_run.id,
                    idempotency_key=f"refund:{build_run.id}",
                )
    except Exception:
        logger.exception("failed to force-fail and refund build", extra={"build_id": build_id})


async def _refund_credits(build_id: str) -> None:
    """Best-effort credit refund on retry exhaustion."""
    try:
        from app.db.repositories.build_run_repository import BuildRunRepository
        from app.db.repositories.credit_repository import CreditRepository
        from app.db.repositories.tenant_repository import TenantRepository
        from app.db.task_session import task_session
        from app.services.credit_service import CreditService

        async with task_session() as session:
            repo = BuildRunRepository(session)
            build_run = await repo.get_by_id(uuid.UUID(build_id))
            if build_run is None:
                return
            tenant = await TenantRepository(session).get_by_id(build_run.tenant_id)
            if tenant is not None:
                credit_svc = CreditService(credits=CreditRepository(session))
                await credit_svc.refund(
                    tenant.org_id,
                    build_run_id=build_run.id,
                    idempotency_key=f"refund:{build_run.id}",
                )
    except Exception:
        logger.exception("failed to refund credits on retry exhaustion", extra={"build_id": build_id})
