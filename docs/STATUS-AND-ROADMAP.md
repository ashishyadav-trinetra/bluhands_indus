# BluHands — Status & Roadmap

> Single source of truth for *what's built, what's partial, and what's next*.
> Last updated: 2026-06-23. Pairs with `PROJECT-MAP.md` (where everything lives)
> and `COMMANDS.md` (how to run it). Decisions/ADRs live in `PROJECT-HANDOFF.md`.

## North star

BluHands is, at its heart, a **capable autonomous AI coding agent** that builds,
self-tests, and ships working apps inside isolated cloud sandboxes. Industry
backends (Medusa for commerce, etc.) are *packaging* on top of that core — later we
market verticals (blu-commerce, blu-crm) that all ride the same agent. So the agent
+ its sandbox + the control plane are the priority; backends are deferred.

---

## ✅ Done (substantially complete)

### Agent (`agent/`) — the autonomous coding agent
- FastAPI service: `/health`, `/clarify`, `/enhance`, `/builds` (start + poll).
- **Reason → Ask → Plan → Build** pipeline:
  - `clarify.py` — asks ≤5 smart MCQ/free-text questions (LLM + offline heuristic).
  - `enhance.py` — turns the one-liner + answers into a production build spec
    (auth/JWT, DB, integrations, scheduled jobs, API security, frontend plan),
    distilling the engineering constitution.
  - `runner.py` — `DryRunRunner` (offline) + `OpenHandsRunner` (6-step real build:
    seed → upload starter → brand → OpenHands build → npm build + serve → Playwright).
- **Sandbox isolation (ADR-10)** — `sandbox.py`: `SandboxProvider`/`SandboxSession`
  Strategy; `LocalSandbox` (dev) + `E2BSandbox` (prod, one gVisor microVM per build,
  killed after). The runner routes **all** file/exec/preview through the session.
- **Backpressure** — `JobStore` caps concurrent builds per replica → 429 + Retry-After.
- **Prod isolation guard** — refuses `LocalSandbox` when `AGENT_ENV=production`.
- **Prebuilt E2B Node template** — `agent/e2b/` (build once with the E2B CLI).
- **Per-role LLM override** — `build_llm(model=…)` uses the model the control-plane sends.
- Supporting modules: `brand.py`, `pipeline.py`, `preview.py`, `medusa_seed.py`,
  `prompt.py`, `llm.py`, `manifests.py`, `tools/` (Playwright verify), `skills/`
  (shadcn, medusa, ecommerce microagents).
- Tests: ~37 offline unit tests + an opt-in real-E2B smoke test.

### Control plane (`control-plane/`) — "Forge"
- Async FastAPI; ~20 endpoints (health, auth, tenants, builds, api-keys, payments,
  admin, domains, agent proxy).
- Services: auth, build, tenant, payment, api-key, credit, admin, domain, Celery dispatcher.
- DB: 9+ tables (SQLAlchemy 2.0 async), 4 Alembic migrations
  (initial, platform_role, llm_model, custom_domain), build FSM, row-locked credits.
- **Auth**: RS256 JWT + refresh rotation + Redis blocklist (machine/admin) **and**
  **Supabase JWT verification** (platform users, ADR-13) — additive.
- **Platform roles** user/admin/tester/self + admin panel API + **per-role model map**.
- Celery build pipeline: QUEUED→LIVE FSM, 3 priority queues, retry/backoff/DLQ,
  soft-timeout → FAILED + auto credit refund.
- Observability: Prometheus `/metrics`, Sentry, structured JSON logs, health probes.
- Tests: ~140 across 24 files; CI (ruff + mypy advisory + alembic smoke + pytest).
- k8s manifests (api HPA 3→20, worker HPA 2→10, Ingress+TLS).

### Frontend (`frontend/`) — customized OpenHands UI
- `forgeClient` axios instance → control-plane; Supabase JWT injected.
- Forge pages: setup (industry pick) + build monitor; home redirects into the flow.

### Apps / starters
- `apps/onboarding/` — 7-step wizard (Account→Business→Brand→Catalog→Domain→Review→Build),
  `MockApi` (offline) + `HttpApi` (wired to control-plane + agent).
- `apps/starters/ecommerce-next/` — golden Next.js storefront the agent edits.

### Deployment
- Unified `docker-compose.yml` (frontend, control-plane api/worker/flower, db, cache,
  storage, agent, prometheus, grafana). Multi-stage non-root Dockerfiles. `STARTUP.md`.

---

## 🟡 Partial / needs finishing

| Item | State | What's missing |
|---|---|---|
| **Frontend ↔ control-plane wire (T-A09b)** | partial | `forgeClient` exists; **~21 old OpenHands services still call socket.io**. Audit which migrate to control-plane REST vs stay. Admin panel UI not built. `VITE_API_BASE_URL` not set in `.env`. |
| **OpenHands-in-sandbox confirmation** | wired, unverified | Run the real-E2B smoke + one real build to confirm the AI's own commands execute *inside* the microVM (not the host). |
| **E2B template** | files ready | Must `e2b template build --name bluhands-node` once before real prod builds. |
| **Payments** | seam | `create_checkout` generates local refs; needs real Stripe/Razorpay API calls. |
| **Domains** | stub | `POST /domains/purchase` returns `{ok:true}` without persistence/Entri. |

---

## 🔜 Roadmap — recommended order

### Now (core agent maturity)
1. **Confirm isolation for real** — build `bluhands-node` template, run
   `python -m agent.scripts.e2b_smoke`, then one real `/builds` with `AGENT_SANDBOX_PROVIDER=e2b`.
   Closes the only open isolation question.
2. **Generalize the runner** (most on-theme) — steps 1–3 of `runner.py` assume Medusa/
   e-commerce. Add a "plain build" path: arbitrary repo/workspace, no seed/brand/starter,
   so BluHands is a *general* coding agent. Keep the storefront path as one preset.
3. **Cold-start mitigation** — bake starter `node_modules` into the E2B template, or a
   small warm sandbox pool. Biggest throughput/UX lever.

### Next (make the product usable end-to-end)
4. **T-A09b** — finish the frontend wire: repoint the build/clarify/enhance flow at the
   control-plane, set `VITE_API_BASE_URL`, build the admin panel page, decide socket.io
   vs REST per old service.
5. **Admin panel UI** — list users + change role (calls `/api/v1/admin/users`).
6. **Payments + domains** — wire real Stripe/Razorpay checkout and Entri purchase.

### Later (verticals + scale)
7. Industry packaging (blu-commerce first): backend catalog + adapter (T-A04/A06).
8. Autoscaling tuning: HPA on queue depth, E2B concurrency limits, warm pool sizing.
9. Per-build cost/quota accounting surfaced to the user.

---

## Known gotchas (save yourself hours)
- Install the agent's heavy extras with **uv**, not pip (openhands dep tree).
- Run `alembic upgrade head` after pulling — migrations 0002/0003 (and 0004) add columns.
- Ports are remapped to avoid clashes: API **8001**, frontend **3300**, MinIO **9101**,
  Postgres **5433** (internal `db:5432`). nginx **8080**.
- `AGENT_SANDBOX_PROVIDER` defaults to `local` (no isolation) — set `e2b` in prod.
- After a control-plane code change, a 404 on a "new" route is usually stale
  `__pycache__` — clear it and restart the container.
