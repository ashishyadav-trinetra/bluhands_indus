# Sandbox Runbook — make agents actually build

Two modes. Start with **local** (works today, for demo) → move to **E2B** (isolated,
for prod/scale). The agent's build pipeline is identical; only *where it executes*
changes (`AGENT_SANDBOX_PROVIDER`).

| Mode | Where the build runs | Isolation | Needs |
|---|---|---|---|
| **local** | inside the agent container (npm/git in-container) | none (dev/demo only) | Node+git in the image (now baked when `INSTALL_AGENT=1`) |
| **e2b** | a fresh gVisor microVM per build | full, ephemeral | E2B account + `bluhands-node` template |

---

## A. Local mode — agents build NOW (demo)

1. Root `.env`:
   ```
   INSTALL_AGENT=1                 # installs the OpenHands SDK stack + Node + git
   AGENT_DRY_RUN=false             # do real builds (not the simulated success)
   AGENT_SANDBOX_PROVIDER=local
   AGENT_ENV=development           # local sandbox is REFUSED when AGENT_ENV=production
   AGENT_MAX_CONCURRENT_BUILDS=2
   OPENROUTER_API_KEY=sk-or-...    # the platform LLM key (admins build on this)
   ```
2. Rebuild the agent (first build is slow — installs openhands-sdk via uv + Node):
   ```
   docker compose up -d --build agent
   docker compose exec api alembic upgrade head     # ensure all migrations applied
   ```
3. **Be an admin** — builds are gated (admin/self/tester only; normal users get 402).
   Seed or promote yourself:
   ```
   docker compose exec api python -m app.cli.seed_admin --email you@x.com --password '...'
   # or set your role to "admin" in /admin/users
   ```
4. Build something from the UI, then watch it run:
   ```
   docker compose logs -f agent
   ```
   You'll see `step 1/6 … step 6/6` and a preview URL. OpenHands edits files in a
   temp workspace, runs `npm install` / `npm run build` / `npm run start`, Playwright
   self-tests, returns the preview.

> Local mode shares the agent container — fine for demos, **no isolation**. Don't
> run untrusted multi-tenant builds this way in prod.

## B. E2B mode — isolated, per-build microVM (prod/scale)

1. Build the Node template once (needs the E2B CLI + your key):
   ```
   npm i -g @e2b/cli
   export E2B_API_KEY=e2b_...
   cd agent/e2b && e2b template build --name bluhands-node && cd ../..
   ```
2. Root `.env`:
   ```
   INSTALL_AGENT=1
   AGENT_DRY_RUN=false
   AGENT_SANDBOX_PROVIDER=e2b
   AGENT_ENV=production
   E2B_API_KEY=e2b_...
   OPENROUTER_API_KEY=sk-or-...
   ```
   `docker compose up -d --build agent`
3. Smoke-test the sandbox path before a real build:
   ```
   docker compose exec agent python -m agent.scripts.e2b_smoke
   ```
   Expect: file round-trip + `node --version` + a preview host + clean teardown.
4. **Known risk to confirm on the first real e2b build:** the runner asks the
   OpenHands SDK to reuse the already-provisioned sandbox
   (`Conversation(sandbox_type="e2b", sandbox_id=…)`). If that version of
   openhands-sdk doesn't attach to a pre-made E2B sandbox, the AI step may fall
   back to local — watch `docker compose logs -f agent` on the first run. If so,
   the fix is to let OpenHands manage its own E2B runtime (or exec OpenHands inside
   the sandbox via `commands`). The npm/git/preview steps already run in-sandbox.

## Troubleshooting "stuck on Building"

- **Stuck at Queued** → worker not running the task, or migrations missing
  (`alembic upgrade head`). Check `docker compose logs --tail=50 worker`.
- **Stuck at Building** → the agent runner is mid-build. `docker compose logs -f agent`
  shows the exact step. Common: `npm: not found` (rebuild agent with `INSTALL_AGENT=1`
  so Node is present), or E2B not configured (no template/key) → switch to local to
  confirm the pipeline, then fix E2B.
- **Build "failed" immediately** → usually `OPENROUTER_API_KEY` missing or
  `AGENT_DRY_RUN` still true, or (e2b) the prod isolation guard refused local.
