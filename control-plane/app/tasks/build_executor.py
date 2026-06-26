"""BuildTaskExecutor — testable FSM logic for the build Celery task.

The executor owns the QUEUED→PROVISIONING→BUILDING→TESTING→REVIEW
state machine. It is a plain class with injected dependencies so it
can be unit-tested without a Celery worker, broker, or real DB.

The Celery task (build_tasks.py) constructs a real executor with live
dependencies and calls ``executor.execute(build_id)`` inside asyncio.run().
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from app.db.models.audit import AuditEvent
from app.db.models.enums import BuildStatus
from app.services.protocols import (
    AuditLoggerProtocol,
    BluHandsAgentClientProtocol,
    BuildRunRepositoryProtocol,
    TenantRepositoryProtocol,
)

logger = logging.getLogger(__name__)

# Allowed FSM transitions enforced before every DB write.
_VALID_TRANSITIONS: dict[BuildStatus, BuildStatus] = {
    BuildStatus.QUEUED: BuildStatus.PROVISIONING,
    BuildStatus.PROVISIONING: BuildStatus.BUILDING,
    BuildStatus.BUILDING: BuildStatus.TESTING,
    BuildStatus.TESTING: BuildStatus.REVIEW,
}

_POLL_INTERVAL = 10     # seconds between agent polls
_POLL_TIMEOUT = 23 * 60  # 23 min; task soft limit is 25 min


class FSMError(RuntimeError):
    """Invalid state transition attempted."""


class BuildTaskExecutor:
    """Orchestrates a single build run through the FSM.

    Args:
        builds:   Repository for reading/writing BuildRun rows.
        tenants:  Repository for loading the tenant (industry + org_id).
        agent:    Client for submitting jobs to the OpenHands agent service.
        audit:    Audit logger for state-change events.
        backends: Optional repository for loading the tenant's backend URL.
    """

    def __init__(
        self,
        *,
        builds: BuildRunRepositoryProtocol,
        tenants: TenantRepositoryProtocol,
        agent: BluHandsAgentClientProtocol,
        audit: AuditLoggerProtocol,
        backends=None,
        github_token_resolver=None,
    ) -> None:
        self._builds = builds
        self._tenants = tenants
        self._agent = agent
        self._audit = audit
        self._backends = backends
        # async (user_id) -> github access token | None (fetched from Nango)
        self._github_token_resolver = github_token_resolver

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def execute(self, build_id: str) -> None:
        """Run the full QUEUED→REVIEW pipeline for one build.

        Raises:
            ValueError: if the build is not found or not in QUEUED state.
            FSMError:   if an invalid transition is attempted.
            Exception:  any unhandled agent/storage error (Celery will retry).
        """
        bid = uuid.UUID(build_id)
        build_run = await self._builds.get_by_id(bid)
        if build_run is None:
            raise ValueError(f"BuildRun {build_id} not found")
        if build_run.status != BuildStatus.QUEUED:
            raise ValueError(
                f"BuildRun {build_id} is in status {build_run.status!r}, expected QUEUED"
            )

        try:
            # QUEUED → PROVISIONING
            await self._transition(build_run, to=BuildStatus.PROVISIONING)

            # Resolve tenant context (industry, backend URL, capability manifest).
            tenant = await self._tenants.get_by_id(build_run.tenant_id)
            industry = tenant.industry.value if tenant else ""

            backend_url: str | None = None
            publishable_key: str = ""
            if self._backends and tenant:
                backend = await self._backends.get_active_for_tenant(tenant.id)
                if backend and backend.api_url:
                    backend_url = backend.api_url

            # Resolve optional GitHub push/pull context (token fetched from Nango).
            github = await self._github_context(build_run)

            # PROVISIONING → BUILDING: submit to agent.
            # The agent service loads the capability manifest by industry itself.
            job_id = await self._agent.start_build(
                build_id,
                prompt=build_run.prompt or "",
                tenant_id=str(build_run.tenant_id),
                industry=industry,
                llm_model=build_run.llm_model,
                backend_url=backend_url,
                publishable_key=publishable_key,
                github=github,
            )
            build_run.conversation_id = job_id
            await self._transition(build_run, to=BuildStatus.BUILDING)

            # BUILDING → TESTING: poll agent until it finishes.
            agent_result = await self._poll_until_done(job_id)
            if agent_result.get("status") != "success":
                raise RuntimeError(
                    f"Agent reported failure: {agent_result.get('error', 'unknown')}"
                )
            await self._transition(build_run, to=BuildStatus.TESTING)

            # TESTING → REVIEW: persist preview URL, ready for owner approval.
            build_run.preview_url = agent_result.get("preview_url")
            await self._transition(build_run, to=BuildStatus.REVIEW)

            await self._audit.record(AuditEvent(
                actor="system:celery",
                org_id=None,
                tenant_id=build_run.tenant_id,
                action="build.review_ready",
                target=build_id,
            ))
            logger.info("build reached REVIEW", extra={"build_id": build_id})

        except Exception as exc:
            await self._fail(build_run, error=str(exc))
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _poll_until_done(self, job_id: str) -> dict:
        """Poll the agent until status is 'success' or 'failed', or timeout."""
        deadline = time.monotonic() + _POLL_TIMEOUT
        while True:
            result = await self._agent.get_status(job_id)
            status = result.get("status")
            if status in {"success", "failed"}:
                return result
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(
                    f"Agent build timed out after {_POLL_TIMEOUT}s (job_id={job_id})"
                )
            await asyncio.sleep(min(_POLL_INTERVAL, remaining))

    async def _github_context(self, build_run) -> dict | None:
        """Build the GitHub push/pull context, resolving the token from Nango.

        Returns None unless the user opted into push or pull on a connected repo.
        The token is fetched fresh (never stored) via the injected resolver.
        """
        repo_url = getattr(build_run, "github_repo_url", None)
        push = getattr(build_run, "github_push", False)
        pull = getattr(build_run, "github_pull", False)
        if not (repo_url and (push or pull)):
            return None
        token = None
        started_by = getattr(build_run, "started_by", None)
        if self._github_token_resolver and started_by:
            token = await self._github_token_resolver(started_by)
        return {
            "repo_url": repo_url,
            "token": token,
            "branch": getattr(build_run, "github_branch", None) or "main",
            "push": bool(push),
            "pull": bool(pull),
        }

    async def _transition(self, build_run, *, to: BuildStatus) -> None:
        expected_from = {v: k for k, v in _VALID_TRANSITIONS.items()}.get(to)
        if build_run.status != expected_from:
            raise FSMError(
                f"Cannot transition {build_run.status!r} → {to!r}; "
                f"expected current status {expected_from!r}"
            )
        await self._builds.transition(build_run, to_status=to)
        logger.info(
            "build FSM transition",
            extra={"build_id": str(build_run.id), "to": to.value},
        )

    async def _fail(self, build_run, *, error: str) -> None:
        """Best-effort transition to FAILED. Does not raise."""
        try:
            await self._builds.transition(
                build_run, to_status=BuildStatus.FAILED, error=error
            )
            await self._audit.record(AuditEvent(
                actor="system:celery",
                org_id=None,
                tenant_id=build_run.tenant_id,
                action="build.failed",
                target=str(build_run.id),
            ))
        except Exception:
            logger.exception(
                "failed to persist FAILED status",
                extra={"build_id": str(build_run.id)},
            )
