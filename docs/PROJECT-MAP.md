# BluHands — Project Map (every directory & what it does)

> Orientation for a new contributor. Top-level first, then each service. Pairs with
> `STATUS-AND-ROADMAP.md` (state) and `COMMANDS.md` (how to run). Some leaf files
> are summarized as groups; the pattern is consistent within a folder.

## Top level — `Projects/bluhands/`

```
bluhands/
├─ frontend/        # The product UI (customized OpenHands; React Router 7 + Vite + Supabase)
├─ control-plane/   # "Forge" — FastAPI orchestrator (tenants, auth, credits, builds, admin)
├─ agent/           # The autonomous coding agent (OpenHands SDK + E2B sandbox)
├─ apps/            # onboarding wizard + golden storefront starter
├─ backends/        # per-industry backend black boxes (Medusa) — deferred for now
├─ monitoring/      # prometheus.yml (scrape config)
├─ docs/            # this doc set + SYSTEM-DESIGN, EXTRACTION-PLAN, handoff/roadmap
├─ docker-compose.yml   # unified dev stack (includes control-plane/docker-compose.yml)
├─ .env.example     # root env for compose (agent + frontend + ops knobs)
├─ STARTUP.md       # step-by-step bring-up
└─ README.md        # overview
```

---

## `agent/` — the autonomous coding agent (priority core)

```
agent/
├─ server.py            # entrypoint: uvicorn agent.app:app (reads AGENT_* env)
├─ Dockerfile           # multi-stage, non-root; INSTALL_AGENT arg toggles OpenHands stack
├─ .dockerignore
├─ pyproject.toml       # base deps + [agent] extra (openhands-sdk/tools, e2b, playwright)
├─ e2b/                 # E2B sandbox template (Node-capable build VM)
│   ├─ e2b.Dockerfile   #   Node 22 + git + build tools on e2bdev/base
│   ├─ e2b.toml         #   template name 'bluhands-node', cpu/mem
│   └─ README.md        #   build/push instructions (e2b template build)
└─ agent/               # the Python package
    ├─ app.py           # FastAPI app: /health, /clarify, /enhance, /builds (+429 backpressure)
    ├─ config.py        # pydantic-settings (AGENT_* env): LLM, sandbox, concurrency, env
    ├─ schemas.py       # request/response models (StartBuild, Clarify, Enhance, …)
    ├─ jobs.py          # JobStore: background build execution + concurrency cap (CapacityError)
    ├─ runner.py        # DryRunRunner + OpenHandsRunner (6-step build, all via SandboxSession)
    ├─ sandbox.py       # SandboxProvider/SandboxSession; LocalSandbox + E2BSandbox + factory + prod guard
    ├─ clarify.py       # reason→ASK: ≤5 MCQ/free-text questions (LLM + offline heuristic)
    ├─ enhance.py       # →PLAN: one-liner+answers → structured production build spec
    ├─ prompt.py        # composes the full build prompt (manifest, brand, features, answers)
    ├─ llm.py           # build_llm() (OpenRouter via LiteLLM) + make_completion() + per-role model
    ├─ brand.py         # applies brand kit → design tokens (globals.css, WCAG contrast)
    ├─ pipeline.py      # prepare workspace from starter + write backend env
    ├─ preview.py       # npm install/build/serve helpers (used by local path)
    ├─ medusa_seed.py   # seed merchant products via Medusa Admin API (storefront preset)
    ├─ manifests.py     # load per-industry capability manifest
    ├─ tools/           # custom agent tools (Playwright screenshot-and-verify)
    ├─ skills/          # microagents: shadcn.md, medusa.md, ecommerce.md (stability/skill packs)
    └─ scripts/
        └─ e2b_smoke.py # real-E2B smoke test (python -m agent.scripts.e2b_smoke)
    tests/              # ~37 offline unit tests + test_e2b_smoke.py (opt-in)
```

**Build flow:** `POST /builds` → `JobStore.start` (cap check) → `OpenHandsRunner.run`
→ `provider.acquire()` (E2B microVM) → upload starter → npm install → OpenHands builds
→ npm build + serve → Playwright self-test → preview URL → `session.close()` (kill VM).

---

## `control-plane/` — "Forge" orchestrator

```
control-plane/
├─ app/
│   ├─ main.py                 # FastAPI app factory, health probes, middleware, exception handlers
│   ├─ api/v1/
│   │   ├─ router.py           # aggregates all v1 routers
│   │   ├─ routes/             # thin HTTP layer:
│   │   │   ├─ health.py       #   /health, /health/live, /health/ready, /metrics
│   │   │   ├─ auth.py         #   register/login/refresh/logout/me
│   │   │   ├─ tenants.py      #   tenant CRUD (org-scoped, RBAC)
│   │   │   ├─ builds.py       #   start/list/get/approve/cancel; computes per-role model
│   │   │   ├─ api_keys.py     #   admin API keys (create/list/revoke)
│   │   │   ├─ payments.py     #   checkout + wallet balance + webhooks
│   │   │   ├─ admin.py        #   admin panel: list users, change platform role
│   │   │   └─ domains.py      #   client domains (subdomain/BYO/purchase — purchase is a stub)
│   │   └─ dependencies/       # DI wiring:
│   │       ├─ auth.py         #   get_current_user (RS256 OR Supabase), require_* RBAC
│   │       ├─ providers.py    #   token manager, hasher, blocklist, supabase verifier, settings
│   │       └─ services.py     #   construct services with request-scoped repos
│   ├─ core/                   # config (pydantic-settings, FORGE_*), security (RS256/Argon2),
│   │                          #   exceptions, authz, metrics, observability, logging
│   ├─ db/
│   │   ├─ models/             # SQLAlchemy: user, organization, membership, tenant, build_run,
│   │   │                      #   wallet, credit, payment, api_key, audit, enums, mixins, base
│   │   ├─ repositories/       # data access (CRUD, pagination, FSM transitions, row locks)
│   │   ├─ session.py / task_session.py  # async session factories (request + Celery)
│   ├─ services/               # business logic (SOLID):
│   │   │                      #   auth, build, tenant, payment, api_key, credit, admin, domain,
│   │   │                      #   celery_dispatcher, protocols (interfaces)
│   ├─ tasks/                  # Celery: celery_app, build_tasks (FSM+retry+refund),
│   │   │                      #   build_executor (testable FSM), agent_client (Stub + Http)
│   ├─ schemas/                # pydantic request/response + envelopes
│   ├─ providers/              # payments (Stripe/Razorpay strategy), redis_client
│   └─ cli/                    # seed_admin (create the first platform admin)
├─ migrations/versions/        # Alembic: 0001_initial, 0002_platform_role,
│                              #   0003_build_llm_model, 0004_custom_domain
├─ tests/                      # ~140 tests (unit + integration via httpx ASGI), fakes.py, factories
├─ docker/                     # api.Dockerfile, nginx/ (dev + prod TLS configs)
├─ k8s/                        # Deployments, HPA, Ingress, ConfigMap, ClusterIssuer
├─ scripts/generate_keys.py    # RS256 keypair into secrets/ (no openssl needed)
├─ docker-compose.yml          # api/worker/flower/db/cache/storage/nginx (included by root compose)
└─ docker-compose.prod.yml     # prod overrides (secrets, limits, pinned tags)
```

**Build dispatch:** `POST …/builds` → `BuildService.start_build` (reserve credits,
persist `BuildRun` with role's `llm_model`) → Celery `build.run_build` →
`BuildTaskExecutor` (FSM) → `HttpAgentClient.start_build(… llm_model)` → the agent.

---

## `frontend/` — the product UI

Customized OpenHands frontend (React Router 7 + Vite + Tailwind 4 + Supabase). Key
additions: `forgeClient` (axios → control-plane, injects Supabase JWT), Forge pages
(`forge/setup`, `forge/build/:orgId/:tenantId/:buildId`), home redirect into the flow.
**Note:** ~21 legacy services still call the old OpenHands socket.io backend — these
need auditing/migration (T-A09b). `build/` is the compiled output; `node_modules/` is
install-time only.

## `apps/`
- `onboarding/` — Next.js wizard (7 steps). `MockApi` (offline) + `HttpApi` (control-plane + agent).
- `starters/ecommerce-next/` — golden storefront the agent edits (Next.js + Tailwind + shadcn + Medusa client).

## `backends/` (deferred)
- `medusa/` — golden e-commerce backend config (Dockerfile, compose, capability manifest).
- Twenty CRM + adapter — README only for now.

## `monitoring/`
- `prometheus.yml` — scrapes the control-plane `/metrics` (agent metrics endpoint is a TODO).

## `docs/`
- `STATUS-AND-ROADMAP.md` · `PROJECT-MAP.md` (this) · `COMMANDS.md` · `SYSTEM-DESIGN.md`
  · `EXTRACTION-PLAN.md` · `PROJECT-HANDOFF.md` · `TASKS.md` · `WORKLOG.md` · `prompts/CODING-STANDARDS.md`.
