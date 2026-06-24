"""Job store + background execution with Redis-backed durability.

Jobs survive agent restarts:
  - L1: in-memory dict  (fast, in-process, lost on restart)
  - L2: Redis hash      (durable, 7-day TTL, optional — graceful fallback to L1 only)

Key pattern: ``bluhands:job:{job_id}``  (TTL: 7 days)

When ``redis_url`` is None or Redis is unreachable, the store silently degrades
to pure in-memory (fine for local dev / CI).  The ``active`` counter always
resets to zero on restart — in-flight builds from a previous process are already
dead, so the counter is correct.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from agent.runner import BuildRunner, BuildSpec
from agent.schemas import JobStatus, StatusResponse

logger = logging.getLogger(__name__)

_JOB_TTL = 7 * 86_400  # seconds — 7 days


class CapacityError(RuntimeError):
    """Raised when the agent is at its max concurrent builds (→ HTTP 429).

    Backpressure: each build holds a real sandbox + LLM spend, so a replica
    accepts only ``max_concurrent`` at once. Upstream (the control-plane Celery
    queue) absorbs the overflow and retries.
    """


class JobStore:
    """Tracks build jobs and runs them in the background, with a concurrency cap.

    Args:
        runner:         The BuildRunner that executes each spec.
        max_concurrent: Hard cap on simultaneous builds per replica.
        redis_url:      Optional Redis URL for durable L2 storage.  When None
                        (default) the store is purely in-memory.
    """

    def __init__(
        self,
        runner: BuildRunner,
        *,
        max_concurrent: int = 4,
        redis_url: str | None = None,
    ) -> None:
        self._runner = runner
        self._mem: dict[str, StatusResponse] = {}   # L1: always present
        self._redis_url = redis_url
        self._redis = None                           # L2: lazy-init, may stay None
        self._tasks: set[asyncio.Task] = set()
        self._max = max(1, max_concurrent)
        self._active = 0

    @property
    def active(self) -> int:
        return self._active

    # ── Redis helpers ──────────────────────────────────────────────────────────

    async def _get_redis(self):
        """Return the Redis client, connecting lazily on first call.

        Returns None (and logs once) if Redis is unavailable or not configured.
        """
        if self._redis is not None:
            return self._redis
        if not self._redis_url:
            return None
        try:
            import redis.asyncio as aioredis  # optional dep

            self._redis = aioredis.from_url(
                self._redis_url, decode_responses=True, socket_connect_timeout=2
            )
            # Verify the connection works right now.
            await self._redis.ping()
            logger.info("JobStore connected to Redis at %s (db=L2)", self._redis_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "JobStore Redis unavailable (%s) — falling back to in-memory only", exc
            )
            self._redis = None
        return self._redis

    async def _save(self, job_id: str, status: StatusResponse) -> None:
        """Write to L1 and best-effort L2 (Redis)."""
        self._mem[job_id] = status
        r = await self._get_redis()
        if r is None:
            return
        try:
            await r.setex(f"bluhands:job:{job_id}", _JOB_TTL, status.model_dump_json())
        except Exception as exc:  # noqa: BLE001
            logger.debug("Redis write failed for job %s: %s", job_id, exc)

    # ── Public API ─────────────────────────────────────────────────────────────

    def _new_job_id(self) -> str:
        return f"job-{uuid.uuid4().hex}"

    async def start(self, spec: BuildSpec) -> str:
        """Create a job and run it in the background; return its job_id.

        Raises:
            CapacityError: if the replica is already running ``max_concurrent``
                builds. No ``await`` precedes the counter bump, so the
                check-then-reserve is atomic on the event loop.
        """
        if self._active >= self._max:
            raise CapacityError(f"agent at capacity ({self._max} concurrent builds)")
        self._active += 1
        job_id = self._new_job_id()
        await self._save(job_id, StatusResponse(status=JobStatus.RUNNING))
        task = asyncio.create_task(self._run(job_id, spec))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job_id

    async def _run(self, job_id: str, spec: BuildSpec) -> None:
        try:
            outcome = await self._runner.run(spec)
        except Exception as exc:  # noqa: BLE001 - record, never crash the loop
            await self._save(
                job_id, StatusResponse(status=JobStatus.FAILED, error=str(exc))
            )
            return
        finally:
            self._active -= 1
        await self._save(
            job_id,
            StatusResponse(
                status=JobStatus.SUCCESS if outcome.success else JobStatus.FAILED,
                preview_url=outcome.preview_url,
                error=outcome.error,
            ),
        )

    async def get(self, job_id: str) -> StatusResponse | None:
        """Return current status, or None if the job is unknown.

        Checks L1 first (fast path). On a miss, falls back to Redis so a
        status poll after an agent restart still resolves correctly.
        """
        if job_id in self._mem:
            return self._mem[job_id]
        # L2 lookup — warm L1 on hit.
        r = await self._get_redis()
        if r is None:
            return None
        try:
            raw = await r.get(f"bluhands:job:{job_id}")
            if raw:
                status = StatusResponse.model_validate_json(raw)
                self._mem[job_id] = status  # warm L1
                return status
        except Exception as exc:  # noqa: BLE001
            logger.debug("Redis read failed for job %s: %s", job_id, exc)
        return None

    async def run_sync(self, spec: BuildSpec) -> tuple[str, StatusResponse]:
        """Start a job and await its completion (used by tests / synchronous flows)."""
        job_id = await self.start(spec)
        # Drain the just-created background task.
        pending = [t for t in self._tasks if not t.done()]
        if pending:
            await asyncio.gather(*pending)
        return job_id, self._mem[job_id]
