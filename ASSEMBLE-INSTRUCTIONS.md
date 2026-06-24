# Task for Claude Code — assemble the clean BluHands monorepo

You are working on a Windows machine. Your job is a **file-copy / assembly task**:
build a clean project folder by copying selected pieces from two existing folders,
excluding heavy junk (virtualenvs, node_modules). **Do not rewrite code** — just
copy trees, verify, and report. Nothing in the source folders may be deleted.

## Paths (absolute)

- SOURCE A (our backend code): `C:\Users\Admin\Documents\Work\Bucket\bluhandsdk\SDK`
- SOURCE B (a cloned OpenHands repo, we only want its frontend):
  `C:\Users\Admin\Documents\Work\Projects\OpenHands`
- DESTINATION (already exists, mostly empty): `C:\Users\Admin\Documents\Work\Projects\bluhands`

## What to copy (KEEP)

Copy these trees into the destination, **excluding** `.venv`, `node_modules`,
`__pycache__`, `.git`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `build`,
`dist`, `.react-router`, `.turbo`, `.next`, and `*.pyc` / `*.log` files:

| From | To |
|---|---|
| `SDK\control-plane` | `bluhands\control-plane` |
| `SDK\bluhands-agent` | `bluhands\agent` |
| `SDK\apps` | `bluhands\apps` |
| `SDK\catalog` | `bluhands\backends` |
| `OpenHands\frontend` | `bluhands\frontend` |
| `SDK\PROJECT-HANDOFF.md`, `SDK\TASKS.md`, `SDK\WORKLOG.md` | `bluhands\docs\` |
| `SDK\prompts` (if present) | `bluhands\docs\prompts` |

Skip any source that doesn't exist (just log it). If a source folder is missing,
do not fail the whole run.

## What NOT to copy (DROP — ~90% of the OpenHands clone)

Everything else in `OpenHands\` is intentionally dropped: `openhands\`,
`openhands-cli\`, `evaluation\`, `microagents\`, `enterprise\`, `tests\`, `docs\`,
`containers\`, `third_party\`, build tooling, `.venv\`. We only want
`OpenHands\frontend`. Reason: our agent is built from the OpenHands **SDK** pip
packages (already pinned in `bluhands\agent\pyproject.toml`), not a fork of the
monorepo.

## How to run

A ready-made idempotent script already exists in the destination:

```powershell
cd C:\Users\Admin\Documents\Work\Projects\bluhands
powershell -ExecutionPolicy Bypass -File scripts\assemble.ps1
```

It uses `robocopy` with the exclusions above. If you prefer, do the equivalent
copies yourself with `robocopy <src> <dst> /E /XD .venv node_modules __pycache__ .git ... /XF *.pyc *.log`.

## Verify after copying

1. Confirm these exist and are non-empty: `bluhands\control-plane\app`,
   `bluhands\agent\agent\app.py`, `bluhands\frontend\package.json`,
   `bluhands\apps`, `bluhands\backends`.
2. Confirm **no** `.venv` or `node_modules` were copied (the copy should be well
   under a few hundred MB):
   ```powershell
   Get-ChildItem -Recurse -Directory C:\Users\Admin\Documents\Work\Projects\bluhands |
     Where-Object { $_.Name -in '.venv','node_modules' }   # should print nothing
   ```
3. (Optional, needs tooling) sanity-build:
   ```powershell
   cd C:\Users\Admin\Documents\Work\Projects\bluhands\agent
   pip install -e ".[dev]"; pytest          # agent unit suite incl. new clarify + sandbox tests
   cd ..\control-plane; pip install -e ".[dev]"; pytest   # 158+ tests
   cd ..\frontend; npm install; npm run typecheck         # then: npm run build
   ```
   Note: install the agent's heavy extras with **uv**, not pip, if pip can't
   resolve them: `uv pip install -e ".[agent]"`.

## Report back

Print a short summary: which trees were copied, total destination size, and the
results of the verify checks (and any test failures). Do **not** attempt to wire
the frontend to the backend or change code — that's a separate task (T-A09,
documented in `bluhands\docs\EXTRACTION-PLAN.md`).
