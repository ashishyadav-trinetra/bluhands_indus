# BluHands — System Design

> Canonical engineering design for the production platform. Reasoning-first: it
> explains *why* each piece exists and how they connect, then the concrete
> contracts. Read alongside `PROJECT-HANDOFF.md` (decisions/ADRs) and
> `prompts/CODING-STANDARDS.md` (the engineering constitution). Where this doc and
> the handoff conflict on a decision, the handoff wins; update both.

## 1. What the system does (and the one hard constraint)

A non-technical merchant signs up, picks an industry, answers a few questions, and
gets a **live, working web app**. The hard constraint that makes this reliable:
**the agent only builds the FRONTEND**; every app is wired to a **pre-built,
battle-tested per-industry backend** (Medusa for e-commerce, etc.). We never let an
LLM build flaky full-stack systems. That single boundary is what lets us promise
"works on day one" at scale.

## 2. Components and responsibilities (single responsibility each)

| Component | Tech | Owns | Talks to |
|---|---|---|---|
| **frontend** | React Router 7 + Vite + Tailwind + Supabase JS | Marketing, pricing, **Supabase login**, onboarding wizard, build-progress UI | control-plane (REST), Supabase (auth) |
| **control-plane** ("Forge") | FastAPI (async), SQLAlchemy 2.0, Alembic | Tenants, RBAC, **credits/billing**, build-job orchestration, secrets, API keys | Postgres, Redis, agent (HTTP), storage (S3) |
| **worker** | Celery 5 (+Flower) | Runs build jobs off the request path; FSM; retries/backoff; refunds | Redis (broker), Postgres, agent (HTTP) |
| **agent** (`bluhands-agent`) | FastAPI + OpenHands SDK + LiteLLM | reason→ask→plan→**build the storefront**, self-test (Playwright) | OpenRouter (LLM), E2B (sandbox), the industry backend (seed) |
| **backends** (catalog) | Medusa, etc. (black boxes) | The real commerce/domain logic the storefront calls | its own DB; exposed via a thin adapter contract |
| **Postgres** | Postgres 15 | Control-plane system-of-record (tenants, builds, wallets, audit) | — |
| **Redis** | Redis 7 | Celery broker/result, JWT blocklist, rate-limit counters, response cache | — |
| **storage** | S3 / MinIO | Build artifacts, logs, exports (private bucket, signed URLs) | — |
| **nginx** | Nginx | TLS, security headers, IP rate-limit, routing `/` → frontend, `/api` → control-plane | all |
| **observability** | Prometheus + Grafana + Sentry | Metrics, dashboards, error tracking + alerting | scrapes all |

Each is independently deployable with its own Dockerfile + env (CODING-STANDARDS §3.1).

## 3. The golden path (data flow)

```
Merchant ──(1 Supabase login)──> frontend
  └─(2 POST /api/v1/.../builds, Supabase JWT)─> control-plane
        ├─(3 verify JWT, check credits: reserve)─> Postgres/Redis
        ├─(4 enqueue build:<uuid>)──────────────> Redis  ──> worker
        │                                                     ├─(5 POST /builds)─> agent
        │                                                     │     ├─(5a /clarify answers folded in)
        │                                                     │     ├─(5b acquire E2B sandbox)─> E2B
        │                                                     │     ├─(5c seed products)──────> backend (Medusa)
        │                                                     │     ├─(5d OpenHands builds FE in sandbox)
        │                                                     │     └─(5e Playwright self-test)─> preview URL
        │                                                     ├─(6 poll GET /builds/{job})─> agent
        │                                                     └─(7 FSM: REVIEW/LIVE; capture credits; store artifacts)
        └─(8 poll GET /api/v1/.../builds/{id})──> control-plane  ──(9 live preview/deploy URL)──> merchant
```

Everything past step 4 is **off the request path** — the HTTP call returns `202`
immediately with a build id; the UI polls. This is what absorbs mass traffic.

## 4. Async-first + the task dispatcher (why we scale)

We expect bursts (CODING-STANDARDS §1: ~500 concurrent launch, ~10k peak). Two
rules make that safe:

1. **Every I/O is async** — asyncpg, httpx (never `requests`), all routes
   `async def`. The API never blocks the event loop, so one API replica serves
   thousands of concurrent *connections* cheaply.
2. **Anything slow (>200ms) is a Celery task**, never inline. A build takes
   minutes and costs LLM money — it absolutely cannot run in a web worker.

**Dispatcher design (Celery + Redis):**
- **Queues by priority:** `high` (paid/interactive), `default`, `low` (retries,
  batch). Routed per task.
- **State machine per build:** `QUEUED → PROVISIONING → BUILDING → TESTING →
  REVIEW → (LIVE|FAILED|CANCELLED)`, persisted in Postgres (`build_runs`), guarded
  so illegal transitions raise (`FSMError`).
- **Reliability:** deterministic task id `build:<uuid>` (idempotent, no dup
  builds); exponential backoff (10·2ⁿ s, max 5); `SoftTimeLimitExceeded` →
  FAILED + **auto-refund credits** via a Celery failure hook; dead-letter for
  poison messages.
- **Scale = add workers, not bigger workers.** Each Celery worker uses
  `--max-tasks-per-child` to bound memory leaks and drains in-flight tasks on
  SIGTERM. Horizontal: K8s HPA on queue depth / CPU.
- **Progress:** the worker writes status transitions to Postgres; the frontend
  polls `GET /api/v1/.../builds/{id}` (cursor-stable). A WebSocket push is a later
  optimization; polling is simplest-correct for launch.

**Why the heavy build runs in the agent, not the worker:** the worker only
*orchestrates* (dispatch, poll, persist, bill). The actual code-generation +
`npm build` runs inside the agent's **E2B sandbox**, so worker hosts stay light
and a runaway build can't take down the platform.

## 5. The sandbox (ADR-10) — isolation that scales

Each build runs in its **own ephemeral E2B microVM** (gVisor isolation),
provisioned then destroyed. **Never docker-in-docker** — DinD doesn't isolate
multi-tenant builds safely and doesn't scale past one fat host. The provider sits
behind `SandboxProvider`/`SandboxSession` (`bluhands-agent/agent/sandbox.py`):
`LocalSandbox` (dev), `E2BSandbox` (prod, `AGENT_SANDBOX_PROVIDER=e2b`). Scale =
the E2B service + the Celery queue/autoscaler. Durable state lives outside the
sandbox: the generated app's Git repo + artifacts in S3 + the persisted OpenHands
conversation.

## 6. Identity, auth & data ownership

**Decision (assumption — confirm): Supabase is the user-identity provider; the
control-plane is a Supabase-JWT-verifying resource server.**
- The frontend already ships Supabase Auth → merchants log in / sign up there.
- The control-plane validates the Supabase access token on every request (verify
  against Supabase JWKS, additive to the existing RS256 system — a new
  `SupabaseAuth` dependency, not a rewrite). Tenancy, RBAC, credits and audit are
  keyed on the Supabase `sub` (user id).
- The control-plane keeps its own **RS256 + API-key** auth for **machine/admin**
  routes (worker→API, admin CLI, partner keys).
- **End-user/domain data is NOT in Supabase** (ADR-6): the **industry backend owns
  it** (Medusa owns shoppers/orders). Supabase is platform-user identity + aux
  storage only. Prefer one Supabase project per client where Supabase holds tenant
  data; shared-project + RLS only if cost forces it (then test RLS adversarially).

**Tenancy/isolation (ADR-7):** generated frontends are public JS and may reach
only their **own tenant-scoped API with a tenant-scoped key**. Business data:
pooled Postgres + RLS (`tenant_id`) for low-risk industries; dedicated DB for
regulated/enterprise — a per-plan policy field, not hardcoded. Cross-tenant leakage
is prevented at the data layer and tested in CI.

**Local dev DB:** plain Docker Postgres (`postgres:15`) — the control-plane's
system-of-record. No managed DB needed locally.

## 7. Security (non-negotiables — CODING-STANDARDS §4)

RS256 access JWT (15 min) + rotating refresh in HttpOnly+Secure+SameSite cookie +
Redis blocklist (for the machine/admin path); Argon2 passwords; API keys stored
SHA-256 only; Pydantic v2 validation on every input; two-layer rate limits (Nginx
IP + app per-user, sliding window, `Retry-After`); security headers + tight CSP +
exact CORS allow-list at Nginx; money/credits mutated atomically (`SELECT FOR
UPDATE` + idempotency keys); secrets only via env/secret-manager, never committed;
audit-log every auth/admin/credit/key action; never leak stack traces.

## 8. Observability, logging & error notification (production-ready)

- **Health:** `/health/live` (always 200), `/health/ready` (DB+Redis+storage),
  `/health`.
- **Metrics (`/metrics`, Prometheus):** request count + p50/p95/p99 latency per
  endpoint, Celery task count by queue/status, build outcomes, credit usage, DB
  pool gauges, Redis hit/miss. **Grafana** dashboards on top.
- **Logs:** structured JSON with `X-Request-ID` correlation across frontend →
  control-plane → worker → agent; secret/PII redaction; levels; ship to a log
  store (Loki/ELK) with ≥90-day retention (security events 1 year).
- **Errors + notification:** global handler → `{success:false, error:{code,
  message}, request_id}`; **Sentry** (PII-scrubbed) captures exceptions; **alerts**
  (Prometheus Alertmanager → Slack/email/PagerDuty) on: 5xx rate, queue depth /
  stuck builds, DB pool saturation, worker crash-loop, credit-refund spikes.
- **Graceful shutdown:** SIGTERM drains in-flight requests/tasks; pools close
  cleanly; `--max-tasks-per-child` bounds worker memory.

## 9. Deployment topology

**Dev:** one `docker-compose.yml` (nginx, frontend, api, worker, flower, agent,
postgres, redis, minio, prometheus, grafana) — `docker compose up` and go.

**Prod (Kubernetes):** each service a Deployment with its own image + env from a
Secret/ConfigMap; HPA on api (3→20) and worker (2→10, scale on queue depth);
anti-affinity; Ingress (TLS via cert-manager); Postgres + Redis managed or
operator-run; MinIO→S3; Prometheus/Grafana/Sentry; the **E2B sandbox is an
external managed service** (no build pods to run). Manifests under
`control-plane/k8s/` (extend with `frontend`/`agent` Deployments).

## 10. Failure modes & how we survive them

| Failure | Containment |
|---|---|
| LLM/agent build fails | FSM → FAILED, **credits auto-refunded**, error surfaced with request_id; no half-charged merchant. |
| Sandbox provider down | Build retries with backoff; circuit-breaker around E2B; queue absorbs the backlog. |
| Traffic spike | API async + 202-then-poll; builds queue; HPA scales api/worker; Nginx IP rate-limit sheds abuse. |
| Backend (Medusa) down at build | Storefront ships with graceful fallback; seed step is best-effort; self-test flags it. |
| Cross-tenant access attempt | Tenant-scoped keys + Postgres RLS; denied at data layer; audited; CI test asserts isolation. |
| Poison build message | Max retries → dead-letter; alert; no infinite loop. |

## 11. What's built vs. what remains

**Built (control-plane Phases 0–7, agent T-A01/07/08/11):** async API, auth+RBAC,
credits + Stripe/Razorpay webhooks, build FSM + Celery dispatcher, S3 storage,
Prometheus/Sentry, k8s manifests, CI, 158+ tests; agent service with
clarification, E2B sandbox provider, live OpenHands build.

**Remaining to connect the three (this epic):**
- **T-A09** — frontend → control-plane REST + Supabase-JWT verifier (the main wire).
- **T-A08b** — route the agent runner *through* the E2B `SandboxSession`.
- Unified top-level compose + `STARTUP.md` (this commit).
- Frontend + agent Deployments added to `k8s/`.
- Alertmanager rules + Grafana dashboards committed.
