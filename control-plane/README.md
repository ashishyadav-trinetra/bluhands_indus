# Forge — Control Plane (Orchestrator)

The multi-tenant control plane for the AI app-building platform: tenants,
identity/RBAC, build-job dispatch (Celery → sandboxed OpenHands), credits, and
billing. FastAPI + PostgreSQL (async) + Redis + Celery.

> Architecture: see [`docs/PHASE-0-ARCHITECTURE.md`](docs/PHASE-0-ARCHITECTURE.md).
> Phase status: **Phase 1 (Foundation) complete** — scaffold, config, DB models +
> migration, core security, health probes, tests. Phases 2–7 to follow.

## Prerequisites

- Docker + Docker Compose, or Python 3.11+ for local runs.

## 1. Generate RS256 JWT keys (required)

Access tokens are signed with an asymmetric RSA keypair. Generate one into
`secrets/` (git-ignored, never committed):

```bash
mkdir -p secrets
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out secrets/jwt_private.pem
openssl rsa -in secrets/jwt_private.pem -pubout -out secrets/jwt_public.pem
```

The paths are already wired in `.env.development`
(`FORGE_JWT_PRIVATE_KEY_PATH` / `FORGE_JWT_PUBLIC_KEY_PATH`). In production,
inject the PEM contents via your secrets manager instead of files.

## 2. Configure environment

```bash
cp .env.example .env      # then edit values
# .env.development holds safe local defaults and is used by docker-compose.
```

## 3. Run with Docker Compose (dev)

```bash
docker compose up --build
```

Services: `api` (8000, hot-reload), `worker` (Celery), `flower` (5555),
`db` (Postgres 5432), `cache` (Redis 6379), `storage` (MinIO 9000/9001),
`nginx` (8080). Health: `http://localhost:8000/health/ready`.

## 4. Database migrations (Alembic)

```bash
# inside the api container (or locally with FORGE_DATABASE_URL set):
alembic upgrade head            # apply migrations
alembic revision --autogenerate -m "describe change"   # create a new one
alembic upgrade head --sql      # preview SQL without applying (offline)
```

## 5. Run locally without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# point FORGE_DATABASE_URL / FORGE_REDIS_URL at local services, then:
uvicorn app.main:app --reload
```

## 6. Tests

```bash
pip install -e ".[dev]"
pytest                # unit + integration (no external services needed)
pytest --cov=app      # with coverage
```

Phase 1 tests cover: password hashing, RS256 token round-trip / wrong-type /
expiry / tamper / reserved-claim protection, token blocklist, API-key hashing,
sliding-window rate limiting, and the health/readiness endpoints.

## Project layout

```
app/
  api/v1/            # routers (thin) + dependencies
  core/              # config, security (JWT/argon2/blocklist), rate limit, logging, middleware, exceptions
  db/                # base, session, mixins, models, repositories
  schemas/           # Pydantic request/response envelopes
  providers/         # external clients (redis; storage/payments/agent in later phases)
  tasks/             # Celery app (tasks added in later phases)
docker/              # api.Dockerfile, nginx config
migrations/          # Alembic env + versions
tests/               # unit + integration
docs/                # architecture
```

## Security notes

- RS256 access tokens (15 min) + refresh tokens (14 d) with rotation + Redis blocklist (Phase 2 wiring).
- Argon2id password hashing. API keys stored as SHA-256 only.
- Every error returns a safe envelope (`code`, `message`, `request_id`) — no stack traces or internals.
- Structured JSON logs with secret redaction. Nginx sets security headers + IP rate limits.
- No secrets in git: `.env*` (except `.example`) and `*.pem` are git-ignored.
