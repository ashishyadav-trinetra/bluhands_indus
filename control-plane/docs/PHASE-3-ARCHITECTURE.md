# Phase 3 — Build Orchestration Architecture Plan

**Service:** `forge` — Control Plane / Build Orchestration layer  
**Author:** Ashish Yadav, Trinetra Labs · **Date:** 18 June 2026 · **Status:** Plan (gates T-301 through T-308)

> Phases 0–2 are complete (40 tests green). This document is the architectural gate for Phase 3.
> Canonical decisions live in `../../PROJECT-HANDOFF.md`. If anything here conflicts, the handoff wins.

---

## 1. Scope and objectives

Phase 3 wires up the build-job orchestration layer of the control plane. After this phase a tenant can:

1. Be created (org-scoped, industry-tagged, isolation-policy set).
2. Request a build — get back a `build_id` immediately (202).
3. Poll or stream the build's progress through a defined FSM.
4. Approve the preview → trigger a deployment transition.

The **BluHands agent** (OpenHands SDK) call is **stubbed** (`BluHandsAgentClient` interface with a fake implementation) — real agent-server wiring is platform epic T-A01. Credit reserve/capture is also **stubbed** (a no-op client call) — real credit deduction is wired in Phase 4 (T-400). Everything else is production-grade.

---

## 2. Data flow: Tenant → Build → Agent → Deploy

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  Client (Next.js / API consumer)                                               │
└───────────────────┬────────────────────────────────────────────────────────────┘
                    │  POST /api/v1/builds  {tenant_id, industry, brand_config,
                    │                        feature_list, idempotency_key}
                    ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│  BuildService.start_build()                                                    │
│   1. Validate tenant exists + active, belongs to caller's org                 │
│   2. Dedup: check idempotency_key in Redis (24h TTL) → return cached if hit   │
│   3. credits_client.reserve(tenant_id, BUILD_COST) [stub Phase 3]             │
│   4. INSERT BuildRun(status=QUEUED, idempotency_key, credit_reserved)         │
│   5. Enqueue Celery task "build.run_build" with task_id = build:{build_id}    │
│   6. Store idempotency_key → build_id in Redis                                │
│   7. Return 202 {build_id, status=QUEUED, poll_url}                           │
└───────────────────┬────────────────────────────────────────────────────────────┘
                    │  Celery broker (Redis queue: build.default)
                    ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│  Celery task: tasks.build.run_build(build_id)                                  │
│                                                                                │
│  QUEUED → PROVISIONING                                                         │
│   • Load BuildRun + Tenant from DB                                             │
│   • Allocate ephemeral workspace context (build config object, no I/O yet)    │
│   • Persist status, emit SSE/pub-sub event                                     │
│                                                                                │
│  PROVISIONING → BUILDING                                                       │
│   • Call BluHandsAgentClient.start_build(config) [stub: returns fake job_id]  │
│   • Persist agent_job_id on BuildRun                                           │
│   • Poll/callback until agent signals done (stub: immediate success)           │
│                                                                                │
│  BUILDING → TESTING                                                            │
│   • Agent's Playwright self-test runs inside its sandbox (stub: pass)         │
│   • Receive test result + screenshot paths                                     │
│                                                                                │
│  TESTING → REVIEW                                                              │
│   • Upload screenshots + build log → S3 ({tenant_id}/builds/{build_id}/...)   │
│   • Generate short-TTL signed URLs for preview                                 │
│   • Persist preview_url, screenshots_urls, status=REVIEW on BuildRun          │
│   • credits_client.capture(build_id) [stub]                                   │
│   • Publish "build.review_ready" event → notification task (build.low)        │
│                                                                                │
│  On any unrecoverable error → FAILED (after retries exhausted)                │
│   • credits_client.refund(build_id) [stub]                                    │
│   • Persist error_message, finished_at                                         │
└───────────────────┬────────────────────────────────────────────────────────────┘
                    │  Owner reviews preview (screenshots + preview URL from S3)
                    ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│  POST /api/v1/builds/{id}/approve  (owner-only, confirm-action header)        │
│   BuildService.approve_build()                                                 │
│   1. Assert status == REVIEW                                                   │
│   2. Transition → DEPLOYING                                                    │
│   3. Enqueue Celery task "build.deploy" (stub: immediate LIVE transition)      │
│   4. Return 202                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼  (Celery task: deploy stub)
              DEPLOYING → LIVE  (live_url persisted; entri.com = T-A04)
```

---

## 3. BuildRun FSM

### 3.1 State definitions

| State | Meaning |
|---|---|
| `QUEUED` | Row created, Celery task enqueued; no work started yet |
| `PROVISIONING` | Celery picked it up; workspace context being assembled |
| `BUILDING` | Agent driving frontend code generation |
| `TESTING` | Agent's Playwright self-tests running |
| `REVIEW` | Build passed; artifacts in S3; awaiting human approval |
| `DEPLOYING` | Approved; deployment in progress |
| `LIVE` | Deployed and accessible (live_url set) |
| `FAILED` | Terminal error (after retries exhausted) |
| `CANCELLED` | Cancelled by owner (only from QUEUED or REVIEW) |

### 3.2 Allowed transitions (enforced in `BuildRunRepository`)

```
QUEUED      → PROVISIONING | FAILED | CANCELLED
PROVISIONING → BUILDING    | FAILED
BUILDING    → TESTING      | FAILED
TESTING     → REVIEW       | FAILED
REVIEW      → DEPLOYING    | CANCELLED
DEPLOYING   → LIVE         | FAILED
```

Any other transition raises `InvalidStateTransitionError` (400 to the caller, 
logged as a WARN — never silently ignored).

### 3.3 Terminal states

`FAILED` and `CANCELLED` are terminal. A new build from a failed/cancelled state 
requires creating a **new** `BuildRun` (a re-run is a new row, preserving history).

### 3.4 Retry semantics

Celery retries are at the **task** level, not the FSM level. The task retries the 
failing step (up to `max_retries=3`, exponential backoff starting at 30 s). Only 
after all retries are exhausted does the task transition the row to `FAILED`.

```
Retry delay = min(30 * 2^attempt, 300)   # cap at 5 min
```

---

## 4. Queue design

### 4.1 Queues

| Queue | Purpose | Concurrency |
|---|---|---|
| `build.high` | Credit refunds, urgent retries | 4 |
| `build.default` | Main build tasks (`run_build`, `deploy`) | 8 |
| `build.low` | Notifications, S3 cleanup | 2 |
| `build.dlq` | Dead-letter (exhausted retries) — consumed by alerting only | 0 |

### 4.2 Task routing

```python
CELERY_TASK_ROUTES = {
    "app.tasks.build.run_build":  {"queue": "build.default"},
    "app.tasks.build.deploy":     {"queue": "build.default"},
    "app.tasks.build.refund":     {"queue": "build.high"},
    "app.tasks.notify.*":         {"queue": "build.low"},
}
```

### 4.3 Timeouts

| Limit | Value | Behaviour |
|---|---|---|
| Soft timeout (`task_soft_time_limit`) | 30 min | `SoftTimeLimitExceeded` → graceful cleanup → transition to FAILED, trigger refund |
| Hard timeout (`task_time_limit`) | 35 min | Force-kill; Celery marks FAILURE; cleanup task on `build.high` runs refund |

### 4.4 Dead-letter handling

After `max_retries` exhausted, Celery re-routes to `build.dlq` via a custom 
`on_failure` hook. A separate alerting consumer (Phase 5 / T-501) reads the DLQ 
and pages the on-call engineer. No automatic reprocessing from DLQ without manual 
inspection.

---

## 5. Idempotency design

### 5.1 Build creation (POST /api/v1/builds)

- Client supplies `X-Idempotency-Key` header (UUID, required).
- Key is stored in Redis as `idempotency:build:{tenant_id}:{key}` → `{build_id}` 
  with TTL = 24 h.
- On duplicate within TTL: return the existing `BuildRun` (200 with the original 
  202-body shape + `X-Idempotent-Replay: true` header). No second row, no second 
  Celery task.
- Idempotency is enforced **before** credit reserve to prevent double-charging.

### 5.2 Credit operations (Phase 4 stubs here)

- Each credit reserve/capture/refund will carry a `wallet_transaction_id` (UUID, 
  generated at call site). The wallet service (Phase 4) will enforce 
  `UNIQUE(idempotency_key)` on `wallet_transactions`. Stubs accept and ignore the key.

### 5.3 Celery task deduplication

- Task ID is set to `build:{build_id}` (deterministic). Celery ignores a second 
  `apply_async` with the same task ID if the first is still in `PENDING/STARTED`.
- Additionally, the Celery task body checks `BuildRun.status != QUEUED` on first 
  line and returns early if the build was already picked up (guards against 
  broker redelivery after acknowledgement failure).

---

## 6. S3 / object storage layout

Bucket: `bluhands-builds` (private; no public ACL anywhere).

```
{tenant_id}/
└── builds/
    └── {build_id}/
        ├── config/
        │   └── build-config.json          # brand kit, feature list, manifest ref
        ├── artifacts/
        │   ├── screenshot-{step}-{n}.png  # Playwright screenshots per step
        │   ├── preview-index.html         # rendered preview (iframe-safe)
        │   └── build-log.txt              # agent stdout/stderr, redacted
        ├── conversation/
        │   └── conversation.json          # persisted OpenHands conversation state
        └── deploy/
            └── frontend.zip               # built Next.js output (for deployment)
```

**Access rules:**
- All objects private; access exclusively via **signed URLs (TTL = 15 min)**.
- `screenshots_urls[]` and `preview_url` on `BuildRun` store **S3 keys**, never 
  signed URLs — signed URLs are generated on demand in the response serialiser.
- Path format includes `{tenant_id}` as the first segment: no path traversal 
  possible; policies can be scoped per-tenant at the IAM/bucket-policy level.
- Filenames are UUIDs or sanitised step names — no user-supplied strings in paths.

---

## 7. New DB models (Phase 3 additions)

### 7.1 `tenants`

```sql
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
org_id          UUID NOT NULL REFERENCES organizations(id)
industry        VARCHAR(64) NOT NULL        -- e.g. "retail", "crm"
isolation_policy VARCHAR(16) NOT NULL       -- "pooled" | "dedicated"
status          VARCHAR(16) NOT NULL DEFAULT 'onboarding'
                -- onboarding | active | suspended | decommissioned
brand_config    JSONB NOT NULL DEFAULT '{}'
backend_type    VARCHAR(64)                 -- e.g. "medusa", "twenty"
backend_manifest JSONB DEFAULT '{}'
created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
deleted_at      TIMESTAMPTZ
UNIQUE (org_id, industry)  -- one active tenant per industry per org (for MVP)
INDEX ON (org_id)
INDEX ON (status)
```

### 7.2 `build_runs`

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
tenant_id        UUID NOT NULL REFERENCES tenants(id)
status           VARCHAR(16) NOT NULL DEFAULT 'queued'
                 -- queued|provisioning|building|testing|review|deploying|live|failed|cancelled
celery_task_id   VARCHAR(128)            -- set when task enqueued
agent_job_id     VARCHAR(128)            -- set when agent called
idempotency_key  VARCHAR(128) NOT NULL
credit_reserved  INTEGER NOT NULL DEFAULT 0
credit_cost      INTEGER NOT NULL DEFAULT 0
preview_url      TEXT                    -- S3 key (not signed URL)
live_url         TEXT
screenshots_urls JSONB DEFAULT '[]'      -- list of S3 keys
error_message    TEXT
started_at       TIMESTAMPTZ
finished_at      TIMESTAMPTZ
created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
deleted_at       TIMESTAMPTZ
UNIQUE (idempotency_key, tenant_id)
INDEX ON (tenant_id)
INDEX ON (status)
INDEX ON (celery_task_id)
```

Alembic migration: `0002_phase3_tenants_builds`.

---

## 8. New service/repository/client interfaces

### 8.1 `TenantRepository` (protocol)
```python
async def create(tenant: TenantCreate) -> Tenant
async def get_by_id(tenant_id: UUID) -> Tenant | None
async def get_by_org(org_id: UUID, *, skip: int, limit: int) -> list[Tenant]
async def update_status(tenant_id: UUID, status: TenantStatus) -> Tenant
```

### 8.2 `BuildRunRepository` (protocol)
```python
async def create(build: BuildRunCreate) -> BuildRun
async def get_by_id(build_id: UUID) -> BuildRun | None
async def get_by_tenant(tenant_id: UUID, *, skip: int, limit: int) -> list[BuildRun]
async def transition_status(
    build_id: UUID, from_status: BuildStatus, to_status: BuildStatus,
    *, extra: dict | None = None,
) -> BuildRun  # raises InvalidStateTransitionError on illegal transition
```

### 8.3 `BluHandsAgentClient` (protocol — stubbed)
```python
async def start_build(config: AgentBuildConfig) -> AgentJob
async def get_job_status(job_id: str) -> AgentJobStatus
async def cancel_job(job_id: str) -> None
```

`FakeBluHandsAgentClient` (used in tests + Phase 3 runtime) immediately returns 
`COMPLETED` with canned screenshot paths.

### 8.4 `CreditClient` (protocol — stubbed)
```python
async def reserve(tenant_id: UUID, amount: int, idempotency_key: str) -> ReserveResult
async def capture(build_id: UUID, idempotency_key: str) -> None
async def refund(build_id: UUID, idempotency_key: str) -> None
```

`StubCreditClient` is a no-op that logs the calls. Replaced by real 
`CreditService` in Phase 4.

### 8.5 `StorageProvider` (protocol — S3 impl in T-306)
```python
async def upload(key: str, data: bytes, content_type: str) -> None
async def signed_url(key: str, ttl_seconds: int = 900) -> str
async def delete(key: str) -> None
```

---

## 9. New API endpoints (Phase 3)

| Method | Path | Task | Auth |
|---|---|---|---|
| POST | `/api/v1/tenants` | T-302 | `require_org_role(OWNER)` |
| GET | `/api/v1/tenants` | T-302 | `require_org_role(MEMBER)` |
| GET | `/api/v1/tenants/{id}` | T-302 | `require_org_role(MEMBER)` |
| POST | `/api/v1/builds` | T-303 | `require_org_role(OWNER)` |
| GET | `/api/v1/builds/{id}` | T-305 | `require_org_role(MEMBER)` |
| GET | `/api/v1/builds/{id}/stream` | T-305 | `require_org_role(MEMBER)` (WS) |
| POST | `/api/v1/builds/{id}/approve` | T-307 | `require_org_role(OWNER)` |
| POST | `/api/v1/builds/{id}/cancel` | T-307 | `require_org_role(OWNER)` |

All return the standard success/error envelope. `POST /builds` returns 202; 
`POST /approve` and `/cancel` return 202 with updated status.

---

## 10. Audit log events (Phase 3 additions)

Every state transition and approval is appended to `audit_logs`:

| Action | Trigger |
|---|---|
| `tenant.created` | TenantService.create |
| `tenant.status_changed` | TenantRepository.update_status |
| `build.started` | BuildService.start_build |
| `build.status_changed` | BuildRunRepository.transition_status |
| `build.approved` | BuildService.approve_build |
| `build.cancelled` | BuildService.cancel_build |

---

## 11. Security checklist (Phase 3 specifics)

- **S3 keys never in URLs**: API always generates a fresh signed URL server-side; 
  clients never receive raw S3 keys.
- **Tenant scoping enforced at repo layer**: `BuildRunRepository` always filters by 
  `tenant_id`; `TenantRepository.get_by_id` verifies `org_id` matches the caller.
- **No user-supplied values in S3 paths**: paths constructed exclusively from 
  UUIDs (`tenant_id`, `build_id`) and hardcoded segment names.
- **`X-Confirm-Action: true` header** required on `POST /approve` (accidental 
  approval guard — same pattern as destructive admin actions).
- **Celery task receives only `build_id`** (UUID), not the full payload — task 
  fetches fresh data from DB (prevents stale/injected payloads in the broker).
- **Soft + hard timeouts** prevent runaway workers from exhausting the pool.
- **DLQ consumption** is read-only monitoring, not automatic reprocessing.

---

## 12. Task breakdown → TASKS.md references

| Task | Deliverable |
|---|---|
| T-301 | `Tenant` model, `TenantRepository`, `TenantService` (create/list/get), unit tests |
| T-302 | Tenant routes + integration tests |
| T-303 | `BuildService.start_build`, `BuildRun` model, Celery task enqueue, unit tests |
| T-304 | Full Celery task skeleton (`run_build`): FSM transitions, retries, timeouts, DLQ, `BluHandsAgentClient` stub |
| T-305 | `GET /builds/{id}` + optional WebSocket stream |
| T-306 | `StorageFactory` + S3 provider + signed-URL generation, tests |
| T-307 | `POST /builds/{id}/approve` + `POST /builds/{id}/cancel`, deployment stub |
| T-308 | Full suite green, handoff update, phase sign-off |
