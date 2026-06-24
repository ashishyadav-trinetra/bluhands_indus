"""Celery application configuration.

Defines the broker/result backend, three priority queues (high/default/low),
sane retry/timeout defaults, and worker hardening. Task implementations
(build dispatch, credit refunds, webhook side-effects) arrive in later phases.
"""

from __future__ import annotations

from celery import Celery
from kombu import Queue

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "forge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.build_tasks"],  # registered task modules
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Reliability defaults.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=1800,          # hard kill at 30 min
    task_soft_time_limit=1500,     # raise SoftTimeLimitExceeded at 25 min
    worker_max_tasks_per_child=100,  # mitigate memory leaks
    worker_prefetch_multiplier=1,    # fair dispatch for long tasks
    result_expires=86400,
    # Priority queues.
    task_default_queue="default",
    task_queues=(
        Queue("high"),
        Queue("default"),
        Queue("low"),
    ),
    task_default_retry_delay=10,
    task_max_retries=5,
)
