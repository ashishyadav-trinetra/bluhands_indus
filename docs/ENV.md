# BluHands — Environment Variables (one place for everything)

Every env var across all services, where it's read, whether it's required, and the
value to use. **⚠ = deploy-critical** (wrong value silently breaks the app — these
are the usual blockers). There are only **two files to edit**:

1. **`/.env`** (repo root) — drives `docker-compose.yml` interpolation: the
   **frontend build** (`VITE_*`), the **agent** (`AGENT_*`, keys), and ops knobs.
2. **`/control-plane/.env.development`** — the control-plane app (`FORGE_*`).

The agent reads `AGENT_*` (+ `OPENROUTER_API_KEY`, `E2B_API_KEY`) which the compose
passes from the root `.env`. The frontend reads `VITE_*` **baked at build time**.

> To see what's ACTUALLY set in a running stack: `bash scripts/dump-env.sh`
> (writes `env-dump.txt` with secrets masked — safe to share for debugging).

---

## Root `/.env` (compose + frontend build + agent)

| Var | ⚠ | Required | Default | What / value |
|---|---|---|---|---|
| `VITE_API_BASE_URL` | ⚠ | **yes (remote)** | `http://localhost:8080` | **Public** URL the BROWSER uses to reach the control-plane (nginx). On a server this MUST be `http(s)://<server-ip-or-domain>:8080` — never localhost. Baked into the JS at build → rebuild frontend after changing. |
| `VITE_SUPABASE_URL` | ⚠ | yes (login) | — | Your Supabase project URL `https://xxxx.supabase.co`. Build-time. |
| `VITE_SUPABASE_ANON_KEY` | ⚠ | yes (login) | — | Supabase anon key (public-safe). Build-time. |
| `INSTALL_AGENT` | ⚠ | for real builds | `0` | `1` installs the OpenHands SDK stack + Node into the agent image (needed for real builds). |
| `AGENT_DRY_RUN` | ⚠ | — | `true` | `false` = run real builds (LLM + sandbox). `true` = simulated success. |
| `AGENT_SANDBOX_PROVIDER` | ⚠ | — | `local` | `local` (in-container, no isolation, demo) or `e2b` (isolated microVM). |
| `AGENT_ENV` | ⚠ | — | `development` | `production` makes the agent REFUSE the local sandbox (forces e2b). |
| `AGENT_E2B_TEMPLATE` | | e2b only | `bluhands-node` | E2B template name (build it: `agent/e2b/`). |
| `AGENT_MAX_CONCURRENT_BUILDS` | | — | `4` | Builds per agent replica before 429 backpressure. |
| `OPENROUTER_API_KEY` | ⚠ | for real builds | — | Platform LLM key (admins build on this). `sk-or-...` |
| `E2B_API_KEY` | ⚠ | e2b only | — | E2B key `e2b_...` |
| `GRAFANA_ADMIN_PASSWORD` | | — | `admin` | Grafana login. |
| `FLOWER_BASIC_AUTH` | | — | `admin:changeme` | Flower (Celery UI) basic auth `user:pass`. |

## Control-plane `/control-plane/.env.development` (prefix `FORGE_`)

| Var | ⚠ | Required | Default | What / value |
|---|---|---|---|---|
| `FORGE_ENV` | | — | `development` | `production` enables strict guards. |
| `FORGE_DATABASE_URL` | ⚠ | yes | `…@localhost:5432/forge` | Use the compose host: `postgresql+asyncpg://forge:forge@db:5432/forge` |
| `FORGE_REDIS_URL` | ⚠ | yes | `redis://localhost:6379/0` | `redis://cache:6379/0` |
| `FORGE_CELERY_BROKER_URL` | | — | `redis://localhost:6379/1` | `redis://cache:6379/1` |
| `FORGE_CELERY_RESULT_BACKEND` | | — | `redis://localhost:6379/2` | `redis://cache:6379/2` |
| `FORGE_CORS_ORIGINS_CSV` | ⚠ | **yes (remote)** | `""` | Comma-list of allowed browser origins. MUST include the frontend origin, e.g. `http://<server-ip>:3300`. Empty = browser CORS-blocks every API call. |
| `FORGE_JWT_PRIVATE_KEY_PATH` / `FORGE_JWT_PUBLIC_KEY_PATH` | ⚠ | yes | — | RS256 keys; `python scripts/generate_keys.py` writes `secrets/` and these point at them (the compose mounts `secrets/`). |
| `FORGE_JWT_ISSUER` / `FORGE_JWT_AUDIENCE` | | — | `forge` / `forge-clients` | |
| `FORGE_ACCESS_TOKEN_TTL_SECONDS` | | — | `900` | |
| `FORGE_SUPABASE_JWKS_URL` | ⚠ | yes (login) | — | `https://xxxx.supabase.co/auth/v1/.well-known/jwks.json` (asymmetric) … |
| `FORGE_SUPABASE_JWT_SECRET` | | or this | — | …OR the project's HS256 JWT secret (legacy). One of the two enables Supabase login. |
| `FORGE_SUPABASE_JWT_AUDIENCE` | | — | `authenticated` | |
| `FORGE_AGENT_MODE` | ⚠ | yes | `stub` | `http` to call the REAL agent (the unified root compose sets this). `stub` = fake success. |
| `FORGE_AGENT_BASE_URL` | ⚠ | — | `http://bluhands-agent:8100` | Compose sets `http://agent:8100`. |
| `FORGE_MODEL_DEFAULT` | | — | `openrouter/anthropic/claude-sonnet-4.5` | LLM for user/admin builds. |
| `FORGE_MODEL_TESTER` | | — | `openrouter/minimax/minimax-01` | LLM for `tester` role. |
| `FORGE_MODEL_SELF` | | — | `openrouter/qwen/qwen-3.6` | LLM for `self` role (self-hosted). |
| `FORGE_FREE_CREDITS_ON_SIGNUP` | | — | `100` | Credits granted on first login. |
| `FORGE_BUILD_CREDIT_COST` | | — | `10` | Credits per build. |
| `FORGE_NANGO_SECRET_KEY` | | GitHub/connectors | — | Nango secret (OAuth layer). |
| `FORGE_NANGO_BASE_URL` | | — | `https://api.nango.dev` | |
| `FORGE_NANGO_GITHUB_PROVIDER_KEY` | | GitHub | `github` | Must match your Nango dashboard provider key. |
| `FORGE_STRIPE_SECRET_KEY` / `FORGE_STRIPE_WEBHOOK_SECRET` | | payments | — | |
| `FORGE_RAZORPAY_KEY_ID` / `_KEY_SECRET` / `_WEBHOOK_SECRET` | | payments | — | |
| `FORGE_ENTRI_API_KEY` / `FORGE_ENTRI_APP_ID` | | domains | — / `bluhands` | |
| `FORGE_SENTRY_DSN` | | — | — | Error tracking (no-op if unset). |
| `FORGE_SEED_ADMIN_EMAIL` / `FORGE_SEED_ADMIN_PASSWORD` | | — | — | Defaults for the `seed_admin` CLI. |

## Infra (set in compose, rarely changed)
Postgres `POSTGRES_USER/PASSWORD/DB=forge`; MinIO `minioadmin/minioadmin`;
Grafana/Prometheus images. Host ports: API→8080 (nginx) & 8001 (direct), frontend
3300, agent 8100, flower 5555, grafana 3001, prometheus 9090, MinIO 9101, Postgres 5433.

---

## The 6 that actually block a remote deploy (set these first)
1. `VITE_API_BASE_URL` = `http://<server>:8080` (root .env) — **rebuild frontend**.
2. `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` (root .env) — **rebuild frontend**.
3. `FORGE_CORS_ORIGINS_CSV` = `http://<server>:3300` (control-plane env).
4. `FORGE_SUPABASE_JWKS_URL` (or `FORGE_SUPABASE_JWT_SECRET`) — login works.
5. `OPENROUTER_API_KEY` + `INSTALL_AGENT=1` + `AGENT_DRY_RUN=false` — real builds.
6. RS256 keys: `python control-plane/scripts/generate_keys.py`.
Then: `docker compose up -d --build frontend agent api worker` + open ports 8080/3300.
