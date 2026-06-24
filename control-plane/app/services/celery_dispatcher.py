"""Concrete Celery build dispatcher.

Wraps ``run_build.apply_async`` behind the ``BuildDispatcherProtocol`` so
``BuildService`` has no direct Celery import and can be tested offline.
"""

from __future__ import annotations

import uuid


class CeleryBuildDispatcher:
    """Dispatches build jobs to the Celery broker."""

    def dispatch(self, build_id: uuid.UUID, *, queue: str = "default") -> str:
        """Enqueue ``build.run_build`` and return the deterministic task ID.

        Uses a deterministic task_id of the form ``build:<build_id>`` so that
        re-submitting the same build (e.g. after an API retry) is idempotent
        at the broker level — Celery will deduplicate by task_id.
        """
        from app.tasks.build_tasks import run_build

        task_id = f"build:{build_id}"
        run_build.apply_async(
            args=[str(build_id)],
            task_id=task_id,
            queue=queue,
        )
        return task_id
