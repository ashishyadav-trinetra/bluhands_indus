# BluHands — Current Status

_Last updated: 2026-06-26. Living doc for humans + agents. Read this first before touching the deployed stack._

Deployment: EC2 `ip-172-31-8-128`, repo at `~/var/www/bluhands_indus` (a clone of the `bluhands` repo). Public URL `https://app.bluehands.ai` (note the **e** — `app.bluehands.ai` is correct; `app.bluhands.ai` without the e is a stale typo still lurking in `.env.production`). Cloudflare sits in front (remember to purge cache after frontend rebuilds).

---

> **2026-06-27 — END-TO-END WORKING.** A build now runs the full path: prompt → smart clarify → enhance → create conversation → agent-server spawns → 52 skills load → agent executes → **output and errors stream live into the conversation view**. GitHub connect + repo picker work natively. The only thing blocking a *successful* build right now is an **empty OpenRouter balance** (the agent's LLM call 402s — and that error is now clearly shown). Top up credits and builds complete. Everything below the "Runtime chain" timeline (items 8–14) is what it took to get the V1 live runtime working behind one public domain.
>
> **One root cause for the remaining rough edges:** with OpenRouter near-zero, every LLM-driven feature degrades silently — the build 402s, the *smart* clarify falls back to generic questions, and conversation auto-titles fall back to the raw prompt (why "Recents" shows full prompts). Add credits → all three come back. Optional hardening: run clarify + titles on a cheap small model so they never degrade (see Known Issues).

## 1. What works right now (2026-06-27)

- **Auth** — Supabase login → forge verifies the JWT via **JWKS** (ES256). `GET /forge/api/v1/auth/me` returns 200 once the token is attached.
- **Settings pages** — LLM, Skills, Secrets, Integrations, etc. render. Backed by the **vendored OSS OpenHands app-server**, not the old `0.38` image.
- **Forced LLM popup** — suppressed (seeded a default platform model so `/api/v1/settings` is 200).
- **Builds run end-to-end** — Start building → `POST /api/v1/app-conversations` → per-conversation **agent-server** spawns (process runtime) → health check passes → **52 skills load** → agent executes → output + errors **stream live** over the conversation WebSocket. The live agent view (App/Changes/Code/Terminal/Planner/Browser) is reachable.
- **Error visibility** — agent failures (e.g. LLM 402 low-balance) now render in the conversation, not a silent "Error occurred."
- **GitHub (native OpenHands)** — connect a PAT in Settings → Integrations; the repo picker lists the user's repos; the agent can clone/push/PR in-sandbox. Nango GitHub duplicate removed.
- **Connectors (Nango)** — the marketplace page loads again (integrations routed back to forge). Connecting still needs a valid `FORGE_NANGO_SECRET_KEY` on the server.

**Blocking a *successful* build today:** empty OpenRouter balance (top up at openrouter.ai/settings/credits).

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

### How a build travels (end-to-end, 2026-06-27)

```
Browser (app.bluehands.ai, via Cloudflare)
  │
  ├─ /                         → frontend container (:3300)  — the SPA
  ├─ /forge/api/v1/*           → forge / control-plane (:8001) — auth, orgs, admin,
  │                                                              agent/clarify, agent/enhance
  ├─ /api/v1/integrations/*    → forge (:8001)               — Nango connector marketplace
  ├─ /api/*  (everything else) → app-server (:3000)          — settings, skills, secrets,
  │                                                              web-client/config, conversations
  ├─ /sockets/*                → app-server (:3000)          — (reserved; main-host sockets)
  └─ /runtime/{port}/*         → agent-server (:{port})      — per-conversation live stream + WS

Build sequence:
1. Prompt → forge /api/v1/agent/clarify  (smart questions; LLM)
2. Answers → forge /api/v1/agent/enhance (production-shaped prompt; LLM)
3. Start building → app-server POST /api/v1/app-conversations  (creates a start task)
4. app-server spawns an agent-server subprocess on a dynamic port (18000+),
   health-checks localhost:{port}/alive, loads skills.
5. Browser opens wss://app.bluehands.ai/runtime/{port}/sockets/events/{id}
   → host nginx → agent-server → agent output + errors stream into the view.
6. Agent runs (LLM = the seeded OpenRouter model); GitHub token (if connected)
   lets it clone/push/PR inside the sandbox.
```

Two LLM budgets to know: the **agent service** (`agent/`, forge FSM — now mostly dormant) and the **app-server's seeded settings LLM** (what conversations actually use). The forge `clarify`/`enhance` calls also use an LLM. All currently point at OpenRouter; all degrade when the balance is empty.

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
8. **`/sockets/` WS route added** to the host nginx (`deploy/nginx-host.conf`) → `:3000`. The conversation event stream (agent output + errors) lives at `wss://host/sockets/events/{id}`; without this it never connects and the build looks silent.
9. **"Start building" never fired the build API — fixed.** `frontend/src/routes/home.tsx` destructured only `isPending` from `useCreateConversation()` and forgot `mutate: createConversation`. So clicking Start building called an **undefined** `createConversation(...)` → `ReferenceError` thrown *before* any request → `POST /api/v1/app-conversations` was never sent, overlay closed, silent bounce back to home. Fixed by destructuring `mutate: createConversation`. **Needs a frontend rebuild** (`docker compose build --no-cache frontend && docker compose up -d frontend` + Cloudflare purge).

---

### Runtime chain — making the live conversation actually run (2026-06-27)

These are the V1-runtime-behind-one-domain fixes, in the order we hit them:

10. **Agent-server health check failed** (`SandboxError: Agent Server Failed to start properly`). The app-server spawns each conversation's agent-server as an **in-container subprocess** (`python -m openhands.agent_server --port N`), then health-checks `localhost:N/alive` — but `replace_localhost_hostname_for_docker` rewrites `localhost → host.docker.internal` (meant for cross-container setups). Fix: `extra_hosts: ["host.docker.internal:127.0.0.1"]` on the `openhands` service so the rewrite points back at the container.
11. **Conversation create 500** — agent init needs **Chromium** for the browser tool. Fix: `playwright install --with-deps chromium` in `openhands-server/Dockerfile`.
12. **Nango integrations 404 (regression)** — routing all `/api/` to the app-server broke forge's bare `/api/v1/integrations`. Fix: a more-specific nginx location sends `/api/v1/integrations` → forge `:8001`.
13. **Live-view WebSocket failed** — the agent-server URL leaked a raw port (`app.bluehands.ai:18001`). Fix: set `SANDBOX_CONTAINER_URL_PATTERN=https://app.bluehands.ai/runtime/{port}` so the browser gets a proxyable URL, plus an nginx regex `location ~ ^/runtime/(\d+)/...` that reverse-proxies to the agent-server port (WS upgrade headers included).
14. **Host nginx couldn't reach the agent-server port** — those ports live inside the `openhands` container, which only published `3000`. Fix: publish range `18000-18030:18000-18030` (assumes the agent-server binds `0.0.0.0`; verify).

## 4b. GitHub = OpenHands-native (decided 2026-06-27)

GitHub is now handled entirely by the OpenHands app-server, not Nango/forge:

- **Connect:** Settings → Integrations (`routes/git-settings.tsx`) → paste a GitHub **PAT** (repo scope) → `POST /api/v1/secrets/provider-tokens` → stored in the app-server secrets store. (OSS mode = PAT; a GitHub OAuth app is an optional later polish.)
- **Use:** the agent clones/pushes/opens PRs **in the conversation sandbox** using that token; `git_router` provides repo search/branches/PRs. Multi-provider (GitHub/GitLab/Bitbucket/Azure/Forgejo) all come for free.
- **Removed:** the duplicate Nango/forge GitHub path in the UI — the `home.tsx` clarify-overlay GitHub section (repo dropdown + push/pull toggles + `useGithubStatus/useGithubRepos`) is gone; the overlay now just links to Settings → Integrations. (Needs frontend rebuild.)
- **Dead but not deleted (intentional):** the forge backend GitHub code (`github_service.py`, the `/github` route, `build_runs.github_*` columns, migration 0006, `build_executor._github_context`) and the `hooks/query/use-github.ts` frontend hook are now unused. Left in place because deleting DB columns/migrations is risky for no benefit. A future cleanup can remove them; nothing calls them.
- **Follow-up (optional):** wire the native repo dropdown into the build start (`createConversation({ repository })` → conversation `selected_repository`) so users can pick an existing repo to build *on* from the UI. Today they connect once, then ask the agent in-conversation.

## 4c. Which agent builds — and where its behaviour is set (IMPORTANT, 2026-06-27)

There are **two** agents; do not confuse them:

- **The real build agent** = the OpenHands **conversation** agent, spawned per build by the **app-server** (`openhands.agent_server`). Its system prompt = SDK template + `system_message_suffix`, built in `live_status_app_conversation_service.py`. The app-server already injects an `<APP_PREVIEW>` block (the `/runtime/{port}` proxy + asset-path recipe) and enables the browser tool. **This is what runs every build.**
- **`agent/agent/`** = the **forge-FSM** agent service (`OpenHandsRunner`, `base_system_prompt.md`). It is **dormant** — builds no longer route through it. Editing its prompt/runner and running `docker compose build agent` has **zero effect** on real builds. (Left in place intentionally in case the FSM path is revived; just don't expect prompt edits there to change builds.)

**BluHands build-behaviour layer (new):** `BLUHANDS_BUILD_RULES` is appended to every code-agent conversation's `system_message_suffix` in `live_status_app_conversation_service.py` — full autonomy (do migrations/env/seed yourself), proxy-aware auth (cookies `Secure`+`SameSite=None`, app-URL env at the proxied URL — fixes "login works in curl, not the browser"), enforced browser verification (screenshot + drive the login flow before finishing), and output discipline. Requires an `openhands` image rebuild.

**`confirmation_mode` / `security_risk` error** is an app-server **conversation setting**, not `agent/runner.py`. Disable the security analyzer (so `security_risk` is no longer mandatory) by seeding it like the LLM — no rebuild:
```bash
curl -sS -X POST http://localhost:3000/api/v1/settings -H "Content-Type: application/json" \
  -d '{"conversation_settings_diff":{"confirmation_mode":false}}'
```

## 4d. Multi-tenancy — per-user isolation (2026-06-27, CRITICAL)

**Was broken:** the app-server ran `DefaultUserAuth` (`get_user_id()` always
`None`), so every Supabase login collapsed to one global user — shared chats,
settings, model, and GitHub identity (`ashish-yadav-911`). forge knew the real
users (admin panel worked); the app-server did not.

**Fix (keystone done in repo):** `supabase_user_auth.py` now verifies **ES256 via
JWKS** in addition to HS256 (your tokens are ES256 — the original HS256-only code
silently fell back to a single `default` user). Setting `SUPABASE_URL` on the
`openhands` service (now wired in compose) is the master switch — `server_config.py`
then selects `SupabaseUserAuth` + per-user Supabase settings/secrets stores, and
conversations scope by `created_by_user_id`.

**Still required on the server (can't be done from the repo):** set
`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`, create the `user_settings` /
`user_secrets` tables in Supabase, deploy, and verify with two accounts. Full
steps in **`deploy/MULTI-TENANCY.md`**. **Do not onboard real users until this is
verified** — until then everyone shares one account.

**Conversation isolation (2026-06-29):** the OSS conversation layer had **no
owner** at all (`created_by_user_id` hardcoded `None`, `_secure_select` filtered
only by `V1`). Patched `sql_app_conversation_info_service.py`: added a `user_id`
column, `_secure_select` now scopes to the authenticated user, and
`save_app_conversation_info` stamps the owner (preserving it on system updates).
**The new column means the conversation DB must be reset** (create_all won't ALTER
an existing table) — delete the app-server SQLite DB / recreate the
`openhands_data` volume on deploy, or every list query errors on the missing
column. Existing (shared) chats are wiped — they're throwaway.

**User name (2026-06-29):** `home.tsx` greeting + sidebar now use the real
identity (`forgeMe.full_name / display_name / email`) instead of the empty
per-user git name, so it shows the person's name, not "User"/"there".

**OpenRouter-key abuse:** now handled *by the isolation itself* — settings are
per-user, so a regular user has no LLM key and cannot use the admin's. The
follow-up is the opposite: **seed the platform model+key into admin users'
settings** so admins can build, while normal users get "upgrade to Pro".

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
