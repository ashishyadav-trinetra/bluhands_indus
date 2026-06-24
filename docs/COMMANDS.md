# BluHands — Commands Cheat-Sheet

> Everything you need to run, inspect, migrate, and test the stack. Windows
> PowerShell shown; macOS/Linux is the same minus `.exe`. Run from the repo root
> (`Projects/bluhands`) unless noted. See `STARTUP.md` for the narrated first-run.

## 0. One-time setup

```powershell
# Root env for the unified compose
Copy-Item .env.example .env
#   → set OPENROUTER_API_KEY, E2B_API_KEY (real builds), VITE_SUPABASE_* (login)

# Control-plane secrets (RS256 keypair) + its env
cd control-plane
python scripts/generate_keys.py            # writes secrets/
Copy-Item .env.example .env.development     # then review
#   ensure: FORGE_DATABASE_URL=postgresql+asyncpg://forge:forge@db:5432/forge
#           FORGE_REDIS_URL=redis://cache:6379/0
cd ..
```

## 1. Docker — bring the stack up/down

```powershell
docker compose up --build           # build + start everything (first run)
docker compose up -d                # start detached
docker compose up -d --build agent  # rebuild + restart just one service
docker compose down                 # stop + remove containers (keeps volumes)
docker compose down -v              # ALSO wipe volumes (Postgres/Redis/MinIO data)
docker compose ps                   # status of all services
docker compose logs --tail=50 -f api        # follow one service's logs
docker compose logs --tail=50 api worker    # several at once
docker compose restart api          # restart one service
docker compose exec api sh          # shell into a running container
```

### Service URLs & ports (after the port remaps)
| Service | URL / port |
|---|---|
| Frontend (the app) | http://localhost:3300 |
| Control-plane API + docs | http://localhost:8001 · http://localhost:8001/docs |
| API via nginx | http://localhost:8080 |
| Agent | http://localhost:8100/health |
| Flower (Celery) | http://localhost:5555 |
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:9090 |
| MinIO console | http://localhost:9101 (minioadmin/minioadmin) |
| Postgres (host) | localhost:5433 (internal `db:5432`) |
| Redis (host) | localhost:6379 |

## 2. Database (Postgres + Alembic)

```powershell
# Apply all migrations (run after first boot and after pulling changes)
docker compose exec api alembic upgrade head

# Create the first platform admin
docker compose exec api python -m app.cli.seed_admin --email admin@trinetralabs.ai --password "ChangeMe123!"

# Migration management
docker compose exec api alembic current               # current revision
docker compose exec api alembic history                # list migrations
docker compose exec api alembic downgrade -1           # roll back one
docker compose exec api alembic revision --autogenerate -m "describe change"   # new migration

# Direct SQL access
docker compose exec db psql -U forge -d forge          # psql shell
#   from your host instead: psql -h localhost -p 5433 -U forge -d forge

# Reset the database (DANGER: wipes data)
docker compose down -v; docker compose up -d; docker compose exec api alembic upgrade head
```

Migrations present: `0001_initial`, `0002_platform_role`, `0003_build_llm_model`,
`0004_custom_domain`.

## 3. Tests

```powershell
# Control-plane (~140 tests)
docker compose exec api pytest
docker compose exec api pytest tests/unit/test_admin_roles.py -q     # one file
docker compose exec api ruff check .                                  # lint

# Agent (~37 offline tests)
docker compose exec agent pytest
#   or locally:  cd agent;  uv pip install -e ".[dev]";  pytest

# Frontend
cd frontend; npm install; npm run typecheck; npm run build; npm run test
```

## 4. Real builds (turn off dry-run) + E2B sandbox

```powershell
# In .env:
#   INSTALL_AGENT=1            # build the agent image WITH the OpenHands stack (uses uv)
#   AGENT_DRY_RUN=false
#   AGENT_SANDBOX_PROVIDER=e2b
#   AGENT_ENV=production       # refuses the unisolated local sandbox
#   OPENROUTER_API_KEY=sk-or-...
#   E2B_API_KEY=e2b_...
docker compose up -d --build agent

# Build the E2B Node template ONCE (needed before real prod builds)
npm install -g @e2b/cli
$env:E2B_API_KEY="e2b_..."
cd agent/e2b; e2b template build --name bluhands-node; cd ../..

# Smoke-test the real sandbox (proves isolation + Node)
cd agent; python -m agent.scripts.e2b_smoke
```

## 5. Manual API pokes

```powershell
# Agent health + clarify
curl http://localhost:8100/health
curl -X POST http://localhost:8100/clarify -H "content-type: application/json" -d "{\"industry\":\"ecommerce\"}"
curl -X POST http://localhost:8100/enhance -H "content-type: application/json" -d "{\"prompt\":\"a whatsapp reminder app\"}"

# Control-plane login (then use the token as: Authorization: Bearer <token>)
curl -X POST http://localhost:8001/api/v1/auth/login -H "content-type: application/json" -d "{\"email\":\"admin@trinetralabs.ai\",\"password\":\"ChangeMe123!\"}"

# Admin: list users / change role (needs an admin bearer token)
curl http://localhost:8001/api/v1/admin/users -H "authorization: Bearer <token>"
curl -X PATCH http://localhost:8001/api/v1/admin/users/<id>/role -H "authorization: Bearer <token>" -H "content-type: application/json" -d "{\"platform_role\":\"tester\"}"
```

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `ports are not available: ... :PORT` | Another process owns it. Either stop it (`docker ps`) or change the published port in the compose file (we already moved API→8001, FE→3300, MinIO→9101). |
| api/worker crash-loop | Missing `control-plane/.env.development` or `secrets/`. Run `generate_keys.py`, set `FORGE_DATABASE_URL`/`FORGE_REDIS_URL` to `db`/`cache` hostnames. |
| 404 on a route you "added" | Stale bytecode — clear `__pycache__` and restart the container. |
| agent image build fails on pip | OpenHands dep tree — the image uses **uv**; ensure `INSTALL_AGENT=1` only when you need real builds. |
| `node: not found` in a build | Build the `bluhands-node` E2B template (§4) or set `AGENT_E2B_TEMPLATE=base` won't have Node. |
| frontend blank page | React Router output may be `build/client`; adjust `frontend/Dockerfile` CMD. |
| `include` not recognized | Upgrade Docker Compose to ≥ v2.20. |

## 7. Production (Kubernetes)

Manifests in `control-plane/k8s/` (api HPA 3→20, worker HPA 2→10, Ingress+TLS via
cert-manager). E2B is an external managed service — no build pods. Add `frontend`
and `agent` Deployments alongside. See `docs/SYSTEM-DESIGN.md` §9.
