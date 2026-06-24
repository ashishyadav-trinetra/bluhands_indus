# Observability (Phase 5)

## Metrics (Prometheus)
- Scrape endpoint: `GET /metrics` (enabled when `FORGE_PROMETHEUS_ENABLED=true`).
- Series exposed:
  - `forge_http_requests_total{method,path,status}` — request count (path = route template, so UUIDs never explode cardinality).
  - `forge_http_request_duration_seconds{method,path}` — latency histogram (p50/p95/p99 via `histogram_quantile`).
  - `forge_celery_tasks_total{task,status}` — build task outcomes (success/retry/failure).
  - `forge_build_runs_total{status}` — terminal build statuses.
  - `forge_credits_consumed_total` — credits captured on build approval.
  - `forge_db_pool_connections_in_use`, `forge_db_pool_size` — sampled at scrape time.
- Implemented in `app/core/metrics.py` (definitions + `PrometheusMiddleware` + `render()`).

### Example PromQL
- p95 latency: `histogram_quantile(0.95, sum(rate(forge_http_request_duration_seconds_bucket[5m])) by (le, path))`
- error rate: `sum(rate(forge_http_requests_total{status=~"5.."}[5m])) / sum(rate(forge_http_requests_total[5m]))`

## Error tracking (Sentry)
- `app/core/observability.py::init_sentry` — no-op unless `FORGE_SENTRY_DSN` is set.
- `send_default_pii=False` + a `before_send` scrubber strip cookies, request bodies, and `Authorization`/`Cookie`/webhook-signature headers. Never ship secrets to Sentry.
- `traces_sample_rate=0.1` by default.

## Celery monitoring (Flower)
- Runs as the `flower` compose service on port 5555.
- **Hardened with HTTP basic auth** via `FLOWER_BASIC_AUTH` (default `admin:changeme` in dev — override in staging/prod).
- Flower must **never** be exposed publicly without auth; in prod put it behind the VPN / internal ingress only.

## Alerting (suggested, wire in Phase 7 / infra)
- High 5xx error rate (>1% over 5m) → page.
- p95 latency > 1s over 10m → warn.
- Celery failure rate spike or DLQ depth > 0 → warn.
- DB pool exhaustion (`in_use` approaching `size`) → warn.
