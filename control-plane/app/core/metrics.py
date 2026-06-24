"""Prometheus metrics: definitions, recording helpers, middleware, renderer.

Single module owns all metric objects (default registry) so there is exactly
one definition per timeseries. The API process records HTTP metrics via
``PrometheusMiddleware``; services/tasks call the small ``inc_*`` helpers.
Pool gauges are sampled lazily at scrape time in ``render()``.
"""

from __future__ import annotations

import time

import structlog
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

_log = structlog.get_logger(__name__)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

HTTP_REQUESTS = Counter(
    "forge_http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
HTTP_LATENCY = Histogram(
    "forge_http_request_duration_seconds",
    "HTTP request latency (seconds)",
    ["method", "path"],
    buckets=_LATENCY_BUCKETS,
)
CELERY_TASKS = Counter(
    "forge_celery_tasks_total", "Celery tasks by name and status", ["task", "status"]
)
CREDITS_CONSUMED = Counter(
    "forge_credits_consumed_total", "Total credits consumed (captured on build approval)"
)
BUILD_RUNS = Counter(
    "forge_build_runs_total", "Build runs by terminal status", ["status"]
)
DB_POOL_IN_USE = Gauge("forge_db_pool_connections_in_use", "DB connections checked out")
DB_POOL_SIZE = Gauge("forge_db_pool_size", "Configured DB pool size")


def record_request(method: str, path: str, status: int, duration_seconds: float) -> None:
    """Record one HTTP request's count and latency."""
    HTTP_REQUESTS.labels(method=method, path=path, status=str(status)).inc()
    HTTP_LATENCY.labels(method=method, path=path).observe(duration_seconds)


def inc_celery_task(task: str, status: str) -> None:
    """Increment the Celery task counter for a given task/status."""
    CELERY_TASKS.labels(task=task, status=status).inc()


def inc_credits_consumed(amount: int) -> None:
    """Increment the credits-consumed counter (no-op for non-positive)."""
    if amount > 0:
        CREDITS_CONSUMED.inc(amount)


def inc_build_terminal(status: str) -> None:
    """Increment the build-runs counter for a terminal status."""
    BUILD_RUNS.labels(status=status).inc()


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Times every request and records count + latency by route template.

    Uses the matched route's path template (not the raw URL) to keep label
    cardinality bounded — UUIDs in the path never become distinct series.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        route = request.scope.get("route")
        path = getattr(route, "path", None) or "unmatched"
        if path != "/metrics":
            record_request(request.method, path, response.status_code, duration)
        return response


def render() -> tuple[bytes, str]:
    """Sample gauges and return (payload, content_type) for the scrape."""
    try:
        from app.db.session import get_engine

        pool = get_engine().pool
        DB_POOL_IN_USE.set(pool.checkedout())
        DB_POOL_SIZE.set(pool.size())
    except Exception:  # noqa: BLE001 - metrics must never break the scrape
        _log.debug("db_pool_metrics_unavailable", exc_info=True)
    return generate_latest(), CONTENT_TYPE_LATEST
