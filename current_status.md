# BluHands — Current Status

_Last updated: 2026-06-26. Living doc for humans + agents. Read this first before touching the deployed stack._

Deployment: EC2 `ip-172-31-8-128`, repo at `~/var/www/bluhands_indus` (a clone of the `bluhands` repo). Public URL `https://app.bluehands.ai` (note the **e** — `app.bluehands.ai` is correct; `app.bluhands.ai` without the e is a stale typo still lurking in `.env.production`). Cloudflare sits in front (remember to purge cache after frontend rebuilds).

---

## 1. What works right now (2026-06-26)

- **Auth** — Supabase login → forge verifies the JWT via **JWKS** (ES256). `GET /forge/api/v1/auth/me` returns 200 once the token is attached. (The first one or two 401s on page load are just pre-token requests.)
- **Settings pages** — LLM, Skills, Secrets, etc. render. Backed by the **vendored OSS OpenHands app-server** (new this session), not the old `0.38` image.
- **Forced LLM popup** — suppressed. A default platform model is seeded so `/api/v1/settings` returns 200 instead of 404.
- **Builds** — dispatch reaches the agent (the MissingGreenlet 500 is fixed). **But failures are not surfaced to the UI** — see Known Issues #1.

---

## 2. Architecture as deployed

Three request planes, split by URL prefix at the **host** nginx (`/etc/nginx/sites-available/bluhands`, mirrored in repo at `deploy/nginx-host.conf`):

| Path prefix | Goes to | Service | Role |
|---|---|---|---|
| `/api/`  | `127.0.0.1:3000` | **openhands app-server** | OpenHands v1 API: settings, agent-schema, skills, secrets, conversations, events, sandboxes |
| `/forge/`| `127.0.0.1:8001` | **forge** (control-plane `api`) | Platform brain: auth, orgs, billing, admin, **builds**, integrations |
| `/`      | `127.0.0.1:3300` | **frontend** | Customized OpenHands UI (Vite SPA) |

Key point learned the hard way: there are **two nginxes**. The host nginx above is the one in the browser path. The **docker** nginx (`:8080`, service `nginx`) is NOT in the public path — don't waste time editing it for routing.

### Services (docker compose, `~/var/www/bluhands_indus`)
- `openhands` — built from `./openhands-server` (see §3). Port 3000. Auth **open** (no `SESSION_API_KEY`).
- `api` (forge) — port 8001→8000. Supabase JWKS auth. Code is bind-mounted with `--reload` (edit on host, no rebuild).
- `worker` (celery), `flower`, `db` (postgres, 5433), `cache` (redis), `storage` (minio).
- `agent` — port 8100. OpenHands **SDK** build agent. OpenRouter LLM; sandbox `local`/`e2b`.
- `frontend` — port 3300. Vite vars are **baked at build time** — rebuild after any `VITE_*` change.
- `nginx` (docker, 8080), `prometheus`, `grafana` — internal/monitoring.

### How the two backends share `/api/v1`
The frontend's openHands axios calls **bare** `/api/v1/...` (→ app-server). The forge axios calls go under the **`/forge/`** prefix. So: bare `/api/` = app-server, `/forge/` = forge. They do not collide as long as the host nginx keeps that split.

---

## 3. The vendored app-server (`openhands-server/`) — new this session

Why: the deployed `ghcr.io/all-hands-ai/openhands:0.38` image does **not** implement `/api/v1/settings*`, `skills`, `secrets` — every such path returned the SPA `index.html`, which is why the UI showed "SDK settings schema unavailable." We replaced it with the real **OSS v1 app-server** from the `Projects/OpenHands` fork.

- `openhands-server/openhands/` — vendored OSS package (1.8M, **no `enterprise/`** — forge owns auth/billing/admin, so enterprise would duplicate it).
- `openhands-server/Dockerfile` — `python:3.12-slim` + Node 22; installs **deps only** (`uv sync --no-install-project`) to dodge poetry-dynamic-versioning's git-tag requirement; imports the package from source via `PYTHONPATH`. Runs `uvicorn openhands.server.listen:app` on 3000 with `SERVE_FRONTEND=false`.
- `openhands-server/README.md` — build/deploy/verify steps.
- Compose `openhands` service rebuilt to `build: ./openhands-server`. Volumes: `openhands_data:/root/.openhands` (settings/secrets), `openhands_workspace:/app/workspace`.

Deploy: `docker compose build openhands && docker compose up -d openhands` (first build is heavy: full openhands dep tree, ~5–15 min).

Settings store is OSS **file-based and global** (single `settings.json` in `openhands_data`). The default LLM was seeded with:
```bash
KEY=$(grep -E '^OPENROUTER_API_KEY=' .env | cut -d= -f2- | tr -d '"[:space:]')
curl -sS -X POST http://localhost:3000/api/v1/settings -H "Content-Type: application/json" \
  -d "{\"agent_settings_diff\":{\"llm\":{\"model\":\"openrouter/anthropic/claude-sonnet-4.5\",\"api_key\":\"$KEY\",\"base_url\":\"https://openrouter.ai/api/v1\"}}}"
```

---

## 4. Timeline of this session's fixes

1. **Build 500 → fixed.** `control-plane/app/api/v1/routes/builds.py`: added `session.refresh(build_run)` before serializing (the `updated_at` expiry triggered a `MissingGreenlet` during pydantic validation, rolling back the whole build).
2. **Diagnosed settings failure.** Proved `0.38` returns HTML (not JSON) for every `/api/v1/settings*` — endpoint genuinely absent in that image.
3. **Decision: vendor OSS app-server** (not enterprise) into the repo. (Full-enterprise was rejected: it duplicates forge's auth/billing on the same Supabase + namespace.)
4. **Built + wired** `openhands-server/` (Dockerfile, compose, volumes, healthcheck on `agent-schema`).
5. **Host nginx routing fixed.** Root cause of "changes do nothing": the browser hits the **host** nginx, which only had `/forge/` and `/`. Added `/api/ → :3000`. (Earlier edits were to the wrong, docker, nginx.) File lives in repo: `deploy/nginx-host.conf`; install with `sudo cp deploy/nginx-host.conf /etc/nginx/sites-available/bluhands && sudo nginx -t && sudo nginx -s reload`.
6. **`web-client/config` fix.** It was falling to the SPA → `app_mode` undefined → the whole `useIsAuthed`→schema chain stalled. Routing all `/api/` to the app-server made it return `{"app_mode":"oss",...}`, unblocking the schema query.
7. **Forced LLM popup fixed.** It fires only when `app_mode==="oss" && GET /settings==404 && !hide_llm_settings` (`sidebar.tsx`). Seeded the default LLM so `/settings` is 200.

---

## 5. Known issues / follow-ups (priority order)

1. **Build failure visibility (HIGH).** When a build fails — e.g. OpenRouter **low balance → LLM 402** — nothing clear surfaces in the UI. Need: agent captures the failure reason → control-plane stores it on the build status → frontend shows a clear error toast/banner (not a silent stop). Today the only way to see why is `docker compose logs -f agent` / `worker`. _Where to work: `agent/agent/runner.py` error propagation → `control-plane` build status model/route → frontend build status handling._
2. **Interactive conversation view / build streaming.** Builds now run as **OpenHands conversations** (the forge FSM `forge-build.tsx` is retired). The agent's progress AND errors (e.g. LLM 402 low-balance) stream over a **WebSocket** at `wss://host/sockets/events/{conversationId}`. Added `/sockets/ → :3000` to the host nginx (`deploy/nginx-host.conf`) so this connects — without it the conversation looked silent (no progress, no errors), which was the "no error visibility" symptom. **Still to verify:** that the app-server's `RUNTIME=process` agent actually executes the conversation end-to-end (it may need the agent-server runtime wired). Check `docker compose logs -f openhands` during a build.
3. **Popup seed is data, not code.** If the `openhands_data` volume is wiped, `/settings` 404s and the popup returns. Durable fix = stop `sidebar.tsx` from auto-opening the modal (needs a frontend rebuild).
4. **`FORGE_SUPABASE_SERVICE_ROLE_KEY`** on the server is set to the placeholder comment text. Set the real key (Supabase → Settings → API).
5. **Subscription + usage metering** for non-admins — not built. Per-role gating exists in forge/agent (admin/self/tester free; plain user → 402 → upgrade popup). Metered billing is net-new (forge-side).
6. **Domain typo** — `.env.production` has `app.bluhands.ai` (missing the **e**). Real domain is `app.bluehands.ai`.

---

## 6. Deploy / ops cheatsheet

```bash
cd ~/var/www/bluhands_indus
git pull                                   # handle .env conflicts per DEPLOYMENT_ISSUES.md #10

# forge api: bind-mounted + --reload → edit on host, then:
docker compose up -d api                   # use up -d, NOT restart (restart keeps old env)

# app-server changes:
docker compose build openhands && docker compose up -d openhands

# host nginx (routing) changes:
sudo cp deploy/nginx-host.conf /etc/nginx/sites-available/bluhands
sudo nginx -t && sudo nginx -s reload

# frontend (VITE_* baked at build time):
docker compose build --no-cache frontend && docker compose up -d frontend
# then Cloudflare → Caching → Purge Everything

# health checks:
curl -s https://app.bluehands.ai/api/v1/settings/agent-schema | head -c 80   # JSON = app-server OK
curl -s https://app.bluehands.ai/api/v1/web-client/config | head -c 60       # {"app_mode":"oss"...}
docker compose logs -f agent worker                                          # build execution
```

See `DEPLOYMENT_ISSUES.md` for the full deploy gotcha list (Cloudflare cache, env conflicts, ES256 auth, etc.).
