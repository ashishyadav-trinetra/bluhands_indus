# BluHands — Current Status

_Last updated: 2026-08-31. Living doc for humans + agents. Read this first, then
**`KT-HANDOVER.md`** for the deep detail (port map, LLM budget, patches, traps)._

Deployment: EC2 `ip-172-31-8-128`, repo at `~/var/www/bluhands_indus`. Public URL
`https://app.bluehands.ai` (note the **e**). Cloudflare in front — purge cache after
frontend rebuilds.

---

> **2026-08-31 — builds run end to end on the self-hosted model.** Prompt → clarify →
> conversation → sandbox → agent builds → live preview → VS Code. The LLM is now
> **self-hosted vLLM** (`qwen3.6-35b-a3b`), not OpenRouter, so the old "top up
> OpenRouter credits" blocker no longer applies to org users.
>
> **The one thing that is genuinely broken: login.** The Supabase project is gone
> (NXDOMAIN). Existing cached sessions still work — which hides it — but no new user
> can sign up or log in. See §5.1. Treat this as the top priority.

---

## 1. What works right now (2026-08-31)

- **Builds** — a conversation spawns a per-conversation agent-server, loads 56 SDK
  skills, and the agent builds in its sandbox with output streaming live.
- **App preview** — the agent binds `$APP_PORT` and the app is reachable at
  `https://app.bluehands.ai/runtime/<port>/`.
- **VS Code tab** — openvscode-server per sandbox, proxied at `/vscode/<port>/`.
- **Conversation titles** — 2–3 word LLM-generated project names.
- **Changes tab** — shows the agent's real diffs.
- **Code persistence** — generated code survives container recreates (named volume).
- **Per-user isolation** — conversations and settings are scoped per Supabase user.
- **Tiered models** — admins on OpenRouter/Claude, `@trinetralabs.ai` users pinned
  to self-hosted Qwen with Settings hidden, everyone else gets nothing.

**Not working:** new-user login/signup (§5.1). **Not configured:** GitHub (§5.2).

---

## 2. Architecture as deployed

Three request planes, split by URL prefix at the **host** nginx
(`/etc/nginx/sites-available/bluhands`, mirrored at `deploy/nginx-host.conf`).

> **There are two nginxes.** The host one above is in the browser path. The **docker**
> `nginx` service (`:8082`) is NOT — don't edit it for routing.

| Path prefix | Goes to | Role |
|---|---|---|
| `/api/v1/integrations` | forge `:8001` | Nango connectors (more specific — wins over `/api/`) |
| `/api/` | app-server `:3000` | settings, skills, secrets, conversations, sandboxes |
| `/forge/` | forge `:8001` | auth, orgs, billing, admin, builds |
| `/runtime/{port}/` | sandbox port | app preview + conversation WebSocket — **prefix stripped** |
| `/vscode/{port}/` | VS Code port | **prefix preserved** + `?tkn=` → cookie translation |
| `/sockets/` | app-server `:3000` | conversation event stream |
| `/` | frontend `:3300` | the SPA |

### Services (docker compose)

- `openhands` — built from `./openhands-server`. Port 3000. **Where our custom logic lives.**
- `api` (forge) — 8001→8000. Bind-mounted with `--reload`, so edit on host + `up -d api`.
- `worker` (celery), `flower`, `db` (postgres 5433), `cache` (redis), `storage` (minio).
- `agent` — port 8100. **DORMANT** — builds do not route through it (see §4c).
- `frontend` — 3300. `VITE_*` baked at build time.
- `nginx` (docker, 8082), `prometheus`, `grafana` — internal/monitoring.

### The sandbox port map

Each conversation = one agent-server subprocess in the `openhands` container:

```
agent-server              18000-18030
app preview   (+10000) -> 28000-28030   exported to the agent as $APP_PORT
VS Code       (+20000) -> 38000-38030
```

All bound to **127.0.0.1 only** — nginx reaches them locally, and they must not be
internet-facing. See `KT-HANDOVER.md` §3 for why `$APP_PORT` must never be replaced
by a literal port.

### Volumes

`openhands_data` (settings/secrets) · `openhands_workspace` ·
`openhands_sandboxes` (**per-conversation sandboxes + all generated code** — without
it, code is destroyed on every recreate and conversations become unresumable).

### Sandbox layout

```
/tmp/openhands-sandboxes/<id>/
├── .agent-state/     # event log, bash history, screenshots (agent bookkeeping)
└── workspace/        # ONLY the agent's generated code
    └── <project>/
```

---

## 3. The vendored app-server (`openhands-server/`)

The shipped `ghcr.io/all-hands-ai/openhands:0.38` image does not implement
`/api/v1/settings*`, `skills` or `secrets`, so we vendored the real OSS v1
app-server. No `enterprise/` — forge owns auth/billing/admin.

- `openhands-server/openhands/` — vendored OSS package, with our modifications.
- `openhands-server/patches/` — runtime monkey-patches on `PYTHONPATH` for every
  process (qwen tool-schema compat, git workspace path remap, short titles).
  See `KT-HANDOVER.md` §6, including the import-binding gotcha.
- `openhands-server/.openhands/microagents/` — build skills. **Never hardcode a port
  here**; use `$APP_PORT`.
- Dockerfile: `python:3.12-slim` + Node 22 + Chromium + openvscode-server 1.98.2.

Changes here need `docker compose build openhands`.

## 4. LLM configuration

Self-hosted vLLM at `http://122.160.253.37:8000/v1`, model `qwen3.6-35b-a3b`,
measured **~31–33 tok/s**.

`LLM_MAX_OUTPUT_TOKENS` (8192) and `LLM_TIMEOUT` (900) are **coupled** — the cap is a
time budget that must fit inside the timeout, while staying large enough for the
agent to write a whole file in one tool call. Both failure modes have been hit in
production; read `KT-HANDOVER.md` §4 before changing either.

> **If the agent hangs, do not reflexively restart vLLM.** The box benchmarked
> healthy at 31–33 tok/s throughout a multi-day outage whose real causes were an
> unreachable endpoint and a mis-sized cap. Check endpoint reachability first.

**`.env` overrides compose defaults** — `${VAR:-default}` only applies when unset.

## 4b. GitHub = OpenHands-native

GitHub is handled by the app-server, not Nango/forge. Users would normally connect a
PAT in Settings → Integrations, but non-admin org users have Settings hidden, so the
platform supplies one: set **`BLUHANDS_GITHUB_TOKEN`** and it is grafted onto every
user's provider tokens (a token the user connected themselves still wins).

Dead but intentionally not deleted: the forge GitHub code (`github_service.py`, the
`/github` route, `build_runs.github_*` columns, migration 0006) and
`hooks/query/use-github.ts`. Nothing calls them.

## 4c. Which agent builds (IMPORTANT)

There are **two** agents; do not confuse them.

- **The real build agent** = the OpenHands **conversation** agent, spawned per build
  by the app-server. Its behaviour is set in
  `live_status_app_conversation_service.py` — `BLUHANDS_BUILD_RULES` and the
  `<APP_PREVIEW>` block. **This is what runs every build.**
- **`agent/agent/`** = the forge-FSM agent service. **Dormant.** Editing its prompts
  and rebuilding has **zero effect** on real builds.

## 4d. Multi-tenancy

`SupabaseUserAuth` is **hardcoded on** in `server_config.py` (the `SUPABASE_URL`
conditional is commented out). Identity still works despite the dead Supabase host
because tokens are **HS256**, verified with `SUPABASE_JWT_SECRET`, which needs no DNS.

Per-user settings live in `/root/.openhands/settings_<user_id>.json`. Conversations
are scoped by `user_id` in `sql_app_conversation_info_service._secure_select()`.

> **Trap:** the admin/system context (`SpecifyUserContext`, `user_id=None`) must
> **bypass** that scoping. It doesn't mean "anonymous" — background jobs such as the
> title callback run under it, and scoping them to unowned rows makes them see
> nothing and crash.

---

## 5. Known issues / follow-ups (priority order)

1. **Login broken for new users — HIGHEST.** Supabase project
   `xkpeexoheupmvmyhiuyv.supabase.co` is **NXDOMAIN**. Cached sessions mask it.
   Options: recreate the project (then rebuild the frontend — `VITE_SUPABASE_URL` is
   baked at build time — plus a Cloudflare purge), or finish
   `feature/postgres-auth-migration`.
2. **GitHub not configured.** Set `BLUHANDS_GITHUB_TOKEN` to a fine-grained PAT
   (org resource owner; Contents R/W, Pull requests R/W, Metadata R; bot account).
   Must be a PAT — App installation tokens expire hourly and are never refreshed
   here. It is one shared identity: all commits appear as that account.
3. **vLLM API key in git history** at `3f2452e` (`benchmark.py`). Rotate if the repo
   is or becomes shared. Removed from the working tree.
4. **Subscription + usage metering** for non-admins — not built.
5. **56 SDK skills** load into every conversation. Progressive disclosure keeps the
   cost modest, but most are irrelevant. `disabled_skills` exists per user.
6. **Pin is read-enforced, not write-enforced.** A pinned user can POST a different
   model and see it echoed back; every conversation still uses Qwen. Rejecting the
   write in `settings_router` would make the UI honest.

---

## 6. Deploy / ops cheatsheet

```bash
cd ~/var/www/bluhands_indus

# ALWAYS name the branch. The checkout sits on main while work lands on
# developement, so a bare `git pull` says "Already up to date" after fetching.
git pull origin developement

docker compose build openhands && docker compose up -d openhands  # app-server/patches/microagents
docker compose up -d openhands                                    # env-only changes
docker compose up -d api worker                                   # forge (bind-mounted)

sudo cp deploy/nginx-host.conf /etc/nginx/sites-available/bluhands
sudo nginx -t && sudo nginx -s reload

docker compose build --no-cache frontend && docker compose up -d frontend
# then Cloudflare → Caching → Purge Everything

# health
curl -s https://app.bluehands.ai/api/v1/settings/agent-schema | head -c 80   # JSON = OK
curl -s https://app.bluehands.ai/api/v1/web-client/config | head -c 60
docker compose exec -T openhands sh -c 'echo "cap=$LLM_MAX_OUTPUT_TOKENS timeout=$LLM_TIMEOUT"'
```

> **Verifying a fix:** never trust the status code alone — the SPA answers **200**
> with its own `index.html` for any unmatched path, so a broken route looks healthy.
> Check the response **body**. Full list of traps in `KT-HANDOVER.md` §10.

See `DEPLOYMENT_ISSUES.md` for the deploy gotcha list and `KT-HANDOVER.md` for
everything else.

---

## 7. History

**June 2026** — vendored the OSS app-server (the `0.38` image lacked `/api/v1/settings*`);
fixed host-nginx routing (`/api/` → `:3000`), the forced-LLM popup, and
`home.tsx` never firing the build API; wired the runtime chain (agent-server health
check via `extra_hosts`, Chromium for the browser tool, `/runtime/{port}` proxy,
published sandbox port ranges); made GitHub OpenHands-native; added per-user
isolation (ES256/JWKS support, conversation ownership).

**August 2026** — moved off the decommissioned Ollama DGX box to self-hosted vLLM;
diagnosed and fixed the "stuck on step 0" class of failures (unreachable endpoint,
then the coupled output-cap/timeout budget); moved LLM config enforcement into
`_configure_llm`; pinned the self-hosted model for org users; installed and proxied
VS Code (including the `vscode-tkn` cookie translation); added sandbox persistence;
bound sandbox ports to localhost; fixed conversation titles; removed the hardcoded
port `8011` from 8 microagents in favour of `$APP_PORT`; separated generated code
from agent bookkeeping; wrote `KT-HANDOVER.md`.
