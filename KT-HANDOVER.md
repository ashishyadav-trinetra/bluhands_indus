# BluHands — Knowledge Transfer / Handover

Written 2026-08-31. Read this before touching the deployed stack. It documents what
is **not** obvious from the code, and the traps that have already cost multiple days.

Companion docs: `BLUHANDS_CONTEXT.md` (architecture decisions), `current_status.md`
(older, partly stale — trust this file where they disagree), `DEPLOYMENT_ISSUES.md`.

---

## 1. What this is

A platform where non-technical users describe an app and an autonomous OpenHands
agent builds it in a sandbox, with a live preview.

| Piece | Path | Role |
|---|---|---|
| **app-server** | `openhands-server/` | Vendored OSS OpenHands v1 API. Owns conversations, settings, sandboxes. **Almost all our custom logic lives here.** |
| **forge** | `control-plane/` | Auth, orgs, billing, admin. FastAPI. |
| **frontend** | `frontend/` | Customised OpenHands UI (Vite SPA). |
| **agent** | `agent/` | Legacy forge-FSM build agent. **DORMANT** — builds do NOT route through it. Editing its prompts has zero effect on real builds. |

Builds run as **OpenHands conversations** inside the app-server, not through `agent/`.

---

## 2. Deployment

EC2 `ip-172-31-8-128`, repo at `~/var/www/bluhands_indus`, public at
`https://app.bluehands.ai` (note the **e**). Cloudflare sits in front — purge cache
after frontend rebuilds.

**There are two nginxes.** The one in the browser path is the **host** nginx
(`/etc/nginx/sites-available/bluhands`, mirrored in repo at `deploy/nginx-host.conf`).
The docker `nginx` service is NOT in the public path — do not waste time editing it.

Routing:

| Path | Upstream |
|---|---|
| `/api/v1/integrations` | forge `:8001` |
| `/api/` | app-server `:3000` |
| `/forge/` | forge `:8001` |
| `/runtime/{port}/` | sandbox port, **prefix STRIPPED** |
| `/vscode/{port}/` | VS Code port, **prefix PRESERVED** |
| `/sockets/` | app-server (conversation event stream) |
| `/` | frontend `:3300` |

---

## 3. The port map (memorise this)

Every conversation gets one sandbox = one agent-server subprocess inside the
**openhands** container. Three ports derive from its agent-server port:

```
agent-server              18000-18030   the sandbox control API
app preview   (+10000) -> 28000-28030   where the built app MUST listen
VS Code       (+20000) -> 38000-38030   openvscode-server
```

All published to **127.0.0.1 only** — nginx reaches them locally and they must not
be internet-facing. Defined in `process_sandbox_service.py`
(`app_preview_port_for()` / `vscode_port_for()`).

### `$APP_PORT` — the single source of truth

`APP_PORT` is exported into each sandbox and equals that sandbox's preview port.
**Every instruction, skill and microagent references `$APP_PORT`, never a literal.**

This matters more than it looks. Previously 8 microagent files hardcoded port `8011`
across 45 lines, `_APP_PREVIEW_PORTS` advertised shared framework ports as
"available hosts", and `<APP_PREVIEW>` said something different again. The agent
received contradictory instructions and burned entire builds — one run spent 235
events hunting for a port that could never work and wrote zero code. Reintroduce a
literal port and you resurrect that bug.

`_APP_PREVIEW_PORTS` is deliberately **empty**. Do not repopulate it: those ports are
unpublished (502 through the proxy) and shared across sandboxes, so one
conversation's preview would serve another conversation's app.

---

## 4. LLM configuration — read before changing any number

**Endpoint:** self-hosted vLLM at `http://122.160.253.37:8000/v1`, model
`qwen3.6-35b-a3b`. Measured ~**31–33 tok/s** decode; prefill ~3.5s at 13k tokens,
~16s at 52k.

### The cap/timeout relationship

`LLM_MAX_OUTPUT_TOKENS` and `LLM_TIMEOUT` are **coupled** and must be changed
together. The cap is really a *time* budget:

```
tokens / tokens-per-second   MUST BE WELL UNDER   timeout
```

Both failure modes have been hit in production:

| Setting | Symptom |
|---|---|
| Cap too **high** — 16000 @ 32 tok/s = 500s vs a 300s timeout | `litellm.Timeout` on every step, retried 5×, so the agent looks **stuck on step 0 for ~30 minutes with nothing logged** |
| Cap too **low** — 4096 | qwen spends the whole budget on reasoning, the tool call is truncated mid-JSON → `Unterminated string ... unparseable JSON`, build dies |

Working values: **`LLM_MAX_OUTPUT_TOKENS=8192`, `LLM_TIMEOUT=900`.** Measured at
8192: `finish=tool_calls`, ~186–244s per step, arguments parse cleanly.

**`.env` overrides compose defaults.** `${VAR:-default}` only applies when the
variable is *unset*, so changing a default in `docker-compose.yml` does nothing if
the variable exists in `.env`. This has bitten us. Always verify what is actually
live:

```
docker compose exec -T openhands sh -c 'echo "cap=$LLM_MAX_OUTPUT_TOKENS timeout=$LLM_TIMEOUT"'
```

### The choke point: `_configure_llm()`

`live_status_app_conversation_service._configure_llm()` **builds a brand-new `LLM`
object from scratch** for every conversation, carrying over only the fields it
explicitly passes. Anything set in user settings but not passed here is **silently
dropped** and reset to SDK defaults.

That is why per-user LLM tuning appeared to do nothing for a long time. If you add
an LLM setting anywhere, add it here too or it will never reach the agent.

---

## 5. User tiers

`openhands-server/openhands/app_server/user_auth/supabase_user_auth.py`

| Who | Gets |
|---|---|
| Email in `BLUHANDS_ADMIN_EMAILS` | OpenRouter/Claude, seeded only if they have no key, **free to change** |
| Non-admin `@<BLUHANDS_SELFHOSTED_DOMAINS>` | Self-hosted Qwen, **PINNED** |
| Everyone else | Nothing (must upgrade) |

**"Pinned" means re-applied on every settings read**, not seeded once. The UI hides
the Settings page for these users, but that is cosmetic — `POST /api/v1/settings` is
still reachable, so the pin is enforced server-side. Note it is enforced on *read*,
not *write*: a user can POST a different model and see it echoed back, while every
conversation still uses Qwen.

The **caps** are gated by **endpoint** (`_runs_on_selfhosted_box`, comparing
`base_url`), not by email. Gating by identity was tried and failed three separate
times — admins share the org domain, already-seeded users skip the seed branch, and
admin-assigned users take a third path. The endpoint is the only reliable signal.

Watch for near-miss emails: `ashish.yadav@` and `ashishyadav@` are different
accounts and land in different tiers.

---

## 6. The patches mechanism

`openhands-server/patches/` is on `PYTHONPATH` for **every** Python process (parent
and all agent-server subprocesses). `sitecustomize.py` runs at interpreter startup
and loads:

| Patch | Fixes |
|---|---|
| `fix_task_tracker.py` | qwen omits `TaskItem.title` and `security_risk` |
| `fix_git_workspace_path.py` | Frontend hardcodes `/workspace/project` (the docker-runtime layout); remaps onto the real process-sandbox workspace so the Changes tab works |
| `fix_short_titles.py` | SDK generates 50-char descriptive titles; we want 2–3 word project names |

**Gotcha when writing patches:** if a caller did `from module import func`, patching
`module.func` will NOT affect it — the name was bound at import time.
`fix_git_workspace_path` has to rebind in three modules for exactly this reason.
Check how the caller imports before assuming your patch took effect.

Patches are baked into the image, so any change needs `docker compose build openhands`.

---

## 7. Sandbox layout

```
/tmp/openhands-sandboxes/<sandbox_id>/
├── .agent-state/          # agent-server bookkeeping — not user-facing
│   ├── conversations/     # event log, screenshots
│   └── bash_events/
└── workspace/             # ONLY the agent's generated code
    └── <project-name>/
```

Backed by the named volume `openhands_sandboxes`. **Without it, every line of
generated code is destroyed on container recreate**, and existing conversations
become unresumable — `_restart_sandbox` only revives a sandbox whose `working_dir`
still exists.

Other volumes: `openhands_data` (settings/secrets), `openhands_workspace`.

---

## 8. VS Code tab

`openvscode-server` v1.98.2, installed to the hardcoded path
`/openhands/.openvscode-server`. The SDK's `VSCodeService` will not look anywhere
else — if the binary is missing it silently disables VS Code with only a warning.

**Auth uses a `vscode-tkn` COOKIE, not the `?tkn=` query param** that the SDK's
`get_vscode_url()` puts in the URL. Verified against the running server:
`?tkn=<token>` → 403 `Forbidden.`, `Cookie: vscode-tkn=<token>` → 200 plus the
workbench HTML. The host nginx bridges this with a `map` that converts `?tkn=` into
the cookie on the first request; the server's own `Set-Cookie` carries the session
for everything after.

The nginx location matches **with or without** a trailing slash. openvscode-server
302s to the slash-less form, and a slash-only regex sends that to the SPA — which
answers 200 with the wrong page, so it looks like it works until you read the body.

---

## 9. Deploy procedures

```bash
cd ~/var/www/bluhands_indus

# ALWAYS name the branch — the server checkout sits on main while work is pushed to
# developement, so a plain `git pull` reports "Already up to date" after fetching.
git pull origin developement

# app-server code / microagents / patches  (baked into the image)
docker compose build openhands && docker compose up -d openhands

# env-only changes
docker compose up -d openhands

# forge (bind-mounted with --reload)
docker compose up -d api worker

# host nginx
sudo cp deploy/nginx-host.conf /etc/nginx/sites-available/bluhands
sudo nginx -t && sudo nginx -s reload

# frontend — VITE_* are baked at BUILD time
docker compose build --no-cache frontend && docker compose up -d frontend
# then Cloudflare -> Caching -> Purge Everything
```

---

## 10. Debugging traps (every one of these has burned real days)

1. **HTTP status is not evidence.** The SPA returns **200 with its own index.html**
   for any unmatched path, so a completely broken route looks healthy. **Check the
   response body**, not `%{http_code}`.
2. **The server checkout goes stale silently.** It is on `main` while work is pushed
   to `developement`; `git pull` says "Already up to date" after fetching new
   commits. Tell-tale: `docker compose up -d` reports "Running" when your change
   should have forced "Recreated".
3. **Probing a sandbox port directly bypasses nginx.** Anything implemented in nginx
   (VS Code cookie translation, path handling) is invisible to
   `curl 127.0.0.1:<port>`. Test through `https://app.bluehands.ai/...`.
4. **`curl -L` drops cookies** unless given a jar (`-c/-b`). Redirect-then-cookie
   flows fail under curl while working fine in a browser.
5. **Ports and tokens change on every restart.** Re-derive them; do not reuse shell
   variables from an earlier session — an empty `$PORT` silently builds a URL that
   matches nothing and lands on the SPA.
6. **The app-server log is not the agent log.** LLM calls, timeouts and tool errors
   live in the agent-server subprocess output and
   `/tmp/openhands-sandboxes/<id>/.agent-state/`, not `docker compose logs openhands`.
7. **An unreachable LLM endpoint logs nothing.** It blocks for the full timeout then
   retries, which is indistinguishable from "the model is slow". Check reachability
   **first**:
   ```bash
   docker compose exec openhands curl -s -m 20 -o /dev/null -w "%{http_code}\n" \
     http://122.160.253.37:8000/v1/models -H "Authorization: Bearer <key>"
   ```

---

## 11. Open issues (priority order)

1. **Login is broken for new users — HIGHEST.** The Supabase project
   (`xkpeexoheupmvmyhiuyv.supabase.co`) is **NXDOMAIN / gone**. Existing cached
   sessions still work, which masks it, but no new signup or login can succeed.
   `SUPABASE_URL` is commented out in `.env` for this reason. Options: recreate the
   Supabase project (then rebuild the frontend — `VITE_SUPABASE_URL` is baked at
   build time — plus a Cloudflare purge), or finish the
   `feature/postgres-auth-migration` branch.
   Note `server_config.py` hardcodes `SupabaseUserAuth` on (the `SUPABASE_URL`
   conditional is commented out), and HS256 verification via `SUPABASE_JWT_SECRET`
   works without DNS — which is why per-user identity still functions today.
2. **GitHub not configured.** Set `BLUHANDS_GITHUB_TOKEN` to a fine-grained PAT
   (resource owner = the org; Contents R/W, Pull requests R/W, Metadata R; ideally
   on a bot account). It is grafted onto every user's provider tokens, which is
   required because non-admin org users have Settings hidden and can never connect
   a repo themselves. **Must be a PAT** — GitHub App installation tokens expire
   hourly and this env var is never refreshed. Caveat: it is one shared identity,
   so all commits appear as that account and every user can reach every repo it can.
3. **The vLLM API key is in git history** at commit `3f2452e` (`benchmark.py`).
   Rotate it if the repo is or becomes shared. It is out of the working tree now —
   the scripts read `BLUHANDS_SELFHOSTED_API_KEY` from the environment.
4. **Multi-tenancy is partial.** Conversations are scoped per user. Note
   `_secure_select` in `sql_app_conversation_info_service.py`: the admin/system
   context (`SpecifyUserContext`, `user_id=None`) must **bypass** scoping, or
   background jobs such as the title callback see nothing and crash.
5. **56 SDK skills load into every conversation.** They use progressive disclosure
   (name + description, not full content) so the token cost is modest, but most are
   irrelevant to this product (`jira-issue-to-pr`, `datadog`, `swift-linux`). A
   per-user `disabled_skills` setting exists if you want to trim them.
6. **`current_status.md` is partly stale** — it predates the vLLM switch, the port
   map, the patches and sandbox persistence.

---

## 12. Quick health check

```bash
docker compose ps
docker compose exec -T openhands sh -c 'echo "cap=$LLM_MAX_OUTPUT_TOKENS timeout=$LLM_TIMEOUT"'
curl -sk https://app.bluehands.ai/api/v1/settings/agent-schema | head -c 60
curl -sk https://app.bluehands.ai/api/v1/web-client/config | head -c 60
```

With a conversation open:

```bash
# which sandbox ports are live
docker compose exec -T openhands /app/.venv/bin/python -c "
import socket
for p in list(range(18000,18031))+list(range(28000,28031))+list(range(38000,38031)):
    s=socket.socket(); s.settimeout(0.2)
    if s.connect_ex(('127.0.0.1',p))==0: print('LISTENING',p)
    s.close()"

# did the agent receive its port?
docker compose exec -T openhands sh -c 'for d in /proc/[0-9]*; do
  tr "\0" "\n" < "$d/environ" 2>/dev/null | grep -m1 "^APP_PORT=" && break; done'
```

Expected: one port from each range, and `APP_PORT=28xxx` matching the agent-server
port + 10000.
