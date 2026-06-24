# Extraction plan — assemble the clean `Projects/bluhands` monorepo

**Goal:** this folder contains only what we ship — the autonomous coding agent
(OpenHands **SDK**, not a fork), the control plane, the apps/catalog, and **your
customized OpenHands frontend** (lovable look + pricing + Supabase login). ~90% of
the OpenHands clone is dropped.

Run `scripts/assemble.ps1` (Windows) or `scripts/assemble.sh`. Both are
**idempotent** and exclude `.venv`, `node_modules`, `__pycache__`, `.git`, build
artifacts.

## KEEP — copied into this folder

| Source (existing, working) | → Destination | Why |
|---|---|---|
| `SDK/control-plane/` | `control-plane/` | Forge: tenants, auth/RBAC, credits, billing, build dispatch. Phases 0–7 done, 158 tests green. |
| `SDK/bluhands-agent/` | `agent/` | The agent service: SDK packages + our tools/skills + reason→ask→plan + **E2B** sandbox. |
| `SDK/apps/` | `apps/` | Onboarding wizard + golden Next.js storefront starter. |
| `SDK/catalog/` | `backends/` | Per-industry backends as black boxes (Medusa-India first). |
| `OpenHands/frontend/` | `frontend/` | **Your** customized UI: React Router 7 + Vite + Tailwind 4 + Supabase auth + pricing. |
| `SDK/*.md` governance | `docs/` | PROJECT-HANDOFF, TASKS, WORKLOG, prompts/CODING-STANDARDS. |

## DROP — everything else in the OpenHands clone (~90%)

Per **ADR-1** we keep only the OpenHands SDK (as pip packages) and your frontend.
From `Projects/OpenHands` we drop: `openhands/` (the Python agent/runtime/server —
replaced by `agent/`), `openhands-cli/`, `evaluation/`, `microagents/`,
`enterprise/`, `tests/`, `docs/`, `containers/`, `third_party/`, build tooling,
`.venv/`. The OpenHands clone is left **untouched** as reference; only `frontend/`
is copied out.

## INTEGRATION WORK after assembly

### T-A09 — wire your frontend to our backend  ⚠️ main task
Your OpenHands frontend speaks **socket.io** to the OpenHands backend; our backend
is **REST** (control-plane + agent start/poll). To make the lovable UI the product
front door:
1. Keep the marketing / pricing / **Supabase login** pages as-is.
2. Repoint the API client (`axios` base URL + the socket layer) from the OpenHands
   server to the control-plane (`/api/v1/...`) and the build-status poll.
3. Reuse the already-built onboarding screens (`apps/onboarding`) or port them in.
4. Supabase (ADR-6): auth/aux only — the industry backend owns end-user + domain
   data. Confirm the frontend's Supabase project is the control-plane's auth source
   or a thin gateway in front of it.

### Sandbox wiring (T-A08b)
`agent/agent/sandbox.py` ships a real **E2B** provider (`E2BSandbox`) behind the
`SandboxProvider`/`SandboxSession` interface. Remaining: route `OpenHandsRunner`
file/exec/preview steps through the `SandboxSession` so a prod build executes
**inside** the E2B sandbox (needs `E2B_API_KEY` + a sandbox image with node). Set
`AGENT_SANDBOX_PROVIDER=e2b` to switch.

## Verify after assembly
```
cd agent          && pip install -e ".[dev]" && pytest      # + new clarify/sandbox tests
cd control-plane  && pip install -e ".[dev]" && pytest      # 158+ tests
cd frontend       && npm install && npm run typecheck && npm run build
```
