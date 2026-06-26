# openhands-server — vendored OSS app-server

The OpenHands **v1 OSS app-server** (`openhands/app_server`), vendored from the
fork. It serves the `/api/v1` routes the frontend needs that `openhands:0.38`
did **not** implement:

- `GET /api/v1/settings`, `POST /api/v1/settings`
- `GET /api/v1/settings/agent-schema`, `/conversation-schema`  ← the "SDK settings schema unavailable" fix
- `GET /api/v1/skills/search`  ← the empty Skills page fix
- `/api/v1/secrets`, `/api/v1/conversations`, `/api/v1/events`, …

It is **not** the enterprise backend. forge (control-plane) remains the platform
brain for auth, billing, admin, and builds. This service runs with **auth open**
(no `SESSION_API_KEY`), so the settings/skills endpoints return JSON; the
frontend's Supabase token is ignored here (forge enforces real auth).

## What's vendored
`openhands/` (1.8M, no enterprise), `pyproject.toml`, `uv.lock`, `config.toml`,
`.openhands/`. The Dockerfile installs **deps only** (`--no-install-project`) and
imports the package from source via `PYTHONPATH` — this avoids the
poetry-dynamic-versioning git-tag requirement at build time.

## Deploy on EC2

From the deploy repo (`~/var/www/bluhands_indus`):

```bash
git pull

# Build the app-server (first build is heavy — pulls the full openhands dep
# tree; allow 5–15 min and a few GB of disk).
docker compose build openhands

# Recreate the service (this drops the old 0.38 container)
docker compose up -d openhands

# Watch it come up
docker compose logs -f openhands     # Ctrl-C once you see uvicorn "Application startup complete"
```

## Verify (the exact thing that was broken)

```bash
# Was HTML before; must now be JSON starting with { "...": ... }
curl -s http://localhost:3000/api/v1/settings/agent-schema | head -c 200; echo

# Through nginx (same must hold)
curl -s http://localhost:8080/api/v1/settings/agent-schema | head -c 200; echo
```

If both print JSON (not `<!DOCTYPE html>`), the LLM/Skills settings pages will
load. Hard-reload the site (Ctrl+Shift+R) and purge Cloudflare cache.

## Scope note
nginx routes `settings|skills|secrets` to this service (already configured).
The **interactive conversation view** (`/api/v1/conversations`, `events`,
`sandboxes`) is a separate follow-up: those paths currently go to forge, and the
forge↔app-server split on `/api/v1/` needs a deliberate routing decision before
the live agent view runs through this backend. Settings/Skills/Secrets work now.
