"""Unit tests for Prometheus metric helpers."""

from __future__ import annotations

from app.core import metrics


def test_record_request_and_render_contains_series() -> None:
    metrics.record_request("GET", "/health/live", 200, 0.01)
    payload, content_type = metrics.render()
    text = payload.decode()
    assert "forge_http_requests_total" in text
    assert "forge_http_request_duration_seconds" in text
    assert "text/plain" in content_type or "openmetrics" in content_type


def test_inc_helpers_do_not_raise() -> None:
    metrics.inc_celery_task("build.run_build", "success")
    metrics.inc_credits_consumed(5)
    metrics.inc_credits_consumed(0)  # no-op
    metrics.inc_build_terminal("review")
    payload, _ = metrics.render()
    text = payload.decode()
    assert "forge_celery_tasks_total" in text
    assert "forge_credits_consumed_total" in text
    assert "forge_build_runs_total" in text
