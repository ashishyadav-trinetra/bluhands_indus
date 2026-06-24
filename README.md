# BluHands — clean, production-ready monorepo

A platform where a non-technical business owner onboards, picks an industry,
answers a few questions, and gets a fully working, deployed web app — built and
self-tested by an autonomous coding agent that **only builds the frontend**
against a pre-built, robust per-industry backend.

Assembled from the working pieces under `…/Bucket/bluhandsdk/SDK` plus the
customized OpenHands frontend (lovable look + pricing + Supabase login). It does
**NOT** contain the OpenHands monorepo — per ADR-1 the agent is built from the
OpenHands **SDK** packages plus our own tools/skills, never a fork.

## Structure

```
bluhands/
├─ frontend/        # Customized OpenHands UI (React Router 7 + Vite + Tailwind 4
│                   # + Supabase auth + pricing). The product front door.
├─ control-plane/   # "Forge" — FastAPI: tenants, auth/RBAC, credits, billing, builds.
├─ agent/           # Autonomous coding agent (OpenHands SDK). reason→ask→plan→build,
│                   # E2B sandbox per build (ADR-10), Playwright self-test.
├─ apps/            # onboarding wizard + golden Next.js storefront starter
├─ backends/        # per-industry backends as black boxes (Medusa first)
├─ docs/            # PROJECT-HANDOFF, TASKS, WORKLOG, CODING-STANDARDS, EXTRACTION-PLAN
└─ docker-compose.yml
```

## Status

Folder is being assembled from the existing working code. The agent, control-plane,
apps and catalog are copied from `SDK/`; `frontend/` is copied from your customized
`OpenHands/frontend/`. See `docs/EXTRACTION-PLAN.md` for what's kept vs dropped and
**T-A09** (wire the frontend's socket.io/axios layer to our REST backend) — the main
task after assembly.

## Documentation

- `docs/STATUS-AND-ROADMAP.md` — what's done, what's partial, what's next (start here).
- `docs/PROJECT-MAP.md` — every directory & file and what it does.
- `docs/COMMANDS.md` — startup, docker, database, tests, E2B — command cheat-sheet.
- `docs/SYSTEM-DESIGN.md` — architecture, data flow, scaling, isolation, auth.
- `STARTUP.md` — narrated first-run. `docs/PROJECT-HANDOFF.md` — locked decisions/ADRs.

## Run (dev)

```
docker compose up --build          # frontend + control-plane + agent + db/cache/storage
```
See `docs/COMMANDS.md` for everything else (migrations, seeding, real builds, tests).
