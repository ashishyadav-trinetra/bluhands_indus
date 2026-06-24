# BluHands — startup guide

Bring the whole platform up with one compose. Tested flow for Windows/PowerShell;
the same commands work on macOS/Linux (drop `.exe`, adjust paths).

## 0. One-time tidy (after the manual paste)

1. Rename the agent folder so it matches the docs/compose:
   `bluhands-agent\` → **`agent\`**.
2. Delete the disposable heavy folders if they came across in the paste (they're
   recreated by `pip install` / `npm install`):
   `agent\.venv`, `control-plane\.venv`, `frontend\node_modules`,
   `frontend\build`, any `__pycache__`.

## 1. Prerequisites

- **Docker Desktop** (Compose v2.20+ — needed for `include:`).
- For real builds: an **OpenRouter** API key and an **E2B** API key.
- A **Supabase** project (for login) — URL + anon key.

## 2. Secrets & env (one-time)

```powershell
# Root env for the unified compose:
Copy-Item .env.example .env
#   edit .env → set OPENROUTER_API_KEY, E2B_API_KEY (for real builds),
#   VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY.

# Control-plane secrets (RS256 keypair, no openssl needed) + its env:
cd control-plane
python scripts/generate_keys.py            # writes secrets/ (JWT keys)
Copy-Item .env.example .env.development     # then review values
cd ..
```

> The control-plane reads `control-plane/.env.development` and `control-plane/secrets/`.
> Postgres maps to host **5433** (internal `db:5432`) to avoid clashing with a
> local Postgres.

## 3. Bring it up

```powershell
docker compose up --build
```

First boot pulls images and builds three local images (control-plane, agent,
frontend). Wait for health checks to go green.

## 4. Initialize the database (first run only)

```powershell
docker compose exec api alembic upgrade head
docker compose exec api python -m app.cli.seed_admin --email admin@trinetralabs.ai --password "ChangeMe123!"
```

## 5. Open the services

| Service | URL |
|---|---|
| Frontend (the app) | http://localhost:3300 |
| Control-plane API + docs | http://localhost:8001 · http://localhost:8001/docs |
| Nginx (API via proxy) | http://localhost:8080 |
| Agent | http://localhost:8100/health |
| Flower (Celery) | http://localhost:5555 |
| MinIO console | http://localhost:9101 (minioadmin/minioadmin) |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin / ${GRAFANA_ADMIN_PASSWORD}) |

## 6. Smoke test the wiring

- Agent alive: `curl http://localhost:8100/health` → `{"status":"ok",...}`.
- Clarification popup data: `curl -X POST http://localhost:8100/clarify -H "content-type: application/json" -d "{\"industry\":\"ecommerce\"}"`.
- Control-plane → agent: it now uses the **HTTP** client (`FORGE_AGENT_MODE=http`,
  `FORGE_AGENT_BASE_URL=http://agent:8100`), so a build dispatched by the worker
  hits the real agent. With `AGENT_DRY_RUN=true` the agent returns a simulated
  success — end-to-end with zero LLM cost.

## 7. Go from dry-run to REAL builds

In `.env` set:
```
INSTALL_AGENT=1                # build the agent image WITH the OpenHands SDK stack
AGENT_DRY_RUN=false
AGENT_SANDBOX_PROVIDER=e2b
OPENROUTER_API_KEY=sk-or-...
E2B_API_KEY=e2b_...
```
then `docker compose up -d --build agent`. The first build is slower (it installs
openhands-sdk via uv). Builds now run the OpenHands agent inside an isolated E2B
sandbox.

> The default image (`INSTALL_AGENT=0`) ships **without** the OpenHands stack so
> the stack comes up fast in dry-run for a smoke test. `pip` cannot resolve
> openhands-sdk's dependency tree — the image uses **uv**, which can.

## 8. Tests

```powershell
docker compose exec api pytest                 # control-plane (158+)
docker compose exec agent pytest               # agent (incl. clarify + sandbox)
cd frontend; npm install; npm run typecheck; npm run build
```

## 9. Troubleshooting

- **Port 5432 clash** → host uses 5433; stop any local Postgres if it still clashes.
- **Route 404 after a code change** → stale bytecode; `find . -name __pycache__ -type d -exec rm -rf {} +` then restart the api/worker container.
- **`include` not recognized** → upgrade Docker Compose to ≥ v2.20.
- **Frontend build serves a blank page** → React Router 7 may output to
  `build/client`; if so, change the frontend `Dockerfile` CMD to serve
  `build/client` (see T-A09).
- **Agent can't build for real** → confirm `OPENROUTER_API_KEY` + `E2B_API_KEY`
  are set and `AGENT_DRY_RUN=false`.

## Production

K8s manifests live in `control-plane/k8s/` (api HPA 3→20, worker HPA 2→10,
Ingress + TLS). Add `frontend` and `agent` Deployments alongside; the E2B sandbox
is an external managed service (no build pods). See `docs/SYSTEM-DESIGN.md` §9.
