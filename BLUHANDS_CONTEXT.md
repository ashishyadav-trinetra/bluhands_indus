# BluHands Repository Context

This document exists to quickly orient any future agents working on this codebase. It documents core architectural changes, constraints, role-based access control (RBAC), API routing fixes, and package management policies applied to the `bluhands_indus` OpenHands integration.

---

## 1. The Agent Architecture & Inference Engine
* **Current Model:** Self-hosted Qwen (`openai/qwen3.6:latest`, LiteLLM slug) served via **Ollama at `http://172.16.16.40:11434/v1`** — this is the compose default and the value actually injected into the prod `openhands` container (verified 2026-08-12; `BLUHANDS_SELFHOSTED_BASE_URL` is unset in the server `.env`, so the default wins). The vLLM box at `122.160.253.37:8000` was benchmarked and is OpenAI-compatible, but is **not** currently wired into prod. Trinetra employees (`*@trinetralabs.ai` non-admin) are auto-seeded with this model; platform admins instead use `claude-sonnet-4.5` on OpenRouter.
* **TPS Requirements:** The baseline speed for the agent to feel "snappy" is **25-30 Tokens Per Second** (measured: 31–33 tok/s on the vLLM box). **Do NOT treat hangs as a frozen GPU queue** — that advice was wrong and would send you restarting a healthy server. The classic symptom (agent stuck on step 0 for ~30 min) was caused by the LLM settings, not the GPU:
  - `max_output_tokens` was 64000 → at 32 tok/s a step takes ~33 min to generate, while `llm.timeout` is 300s → `litellm.Timeout`, retried 5×, agent never left step 0.
  - Fixed with `_SELFHOSTED_STEP_CAPS` in `openhands-server/openhands/app_server/user_auth/supabase_user_auth.py`: `max_output_tokens=4096` (~128s/step, provider-agnostic safety net), `reasoning_effort=low`, `enable_thinking=False` via `chat_template_kwargs` (verified on vLLM; Ollama may ignore it), `max_input_tokens=200000`. Caps are re-applied in memory on **every** settings read (users seeded before the caps existed never re-trigger the seed), and on the admin-assignment path for self-hosted URLs. Platform admins are excluded.
* **Agent Flow:** We use OpenHands' default `CodeActAgent` architecture. It relies on a linear ReAct loop inside the Docker sandbox.

---

## 2. Multi-Tier RBAC & Settings Access Control

We implemented a 3-tier user access model across the frontend and backend:

### Role Tiers
1. **Platform Admin (`admin@trinetralabs.ai`)**:
   - Sees **all settings tabs** (LLM, Condenser, Verification, MCP, Skills, Integrations, App, Secrets, API Keys).
   - Has access to **Basic / Advanced / All** view toggles on the LLM page.
   - Auto-seeded with the platform OpenRouter model (`claude-sonnet-4.5` + company OpenRouter API key).
2. **Normal Users (`user@gmail.com` or any standard email)**:
   - Sees **only** the `/settings` (LLM) page in **Basic view**. All other sub-routes (Condenser, Verification, MCP, etc.) are stripped from the sidebar.
   - Can select custom providers (OpenRouter, OpenAI, etc.), enter their own API key, and choose models from dropdowns.
3. **Trinetra Employees (`*@trinetralabs.ai` non-admin)**:
   - Settings sidebar link is completely hidden. Route guards redirect `/settings` attempts to `/`.
   - Backend auto-seeds their settings with the self-hosted Qwen model (`openai/qwen3.6:latest` on DGX box `http://172.16.16.40:11434/v1`), so no API key or configuration is required.

### Files Modified & Rationale
* **`frontend/src/utils/settings-utils.ts`**: Rewrote `isSettingsPageHidden()` to enforce the 3-tier rules cleanly.
* **`frontend/src/hooks/use-settings-nav-items.ts`**: Fixed `forgeMe` email property path (`forgeMe.user.email`) and added fallback to `getUserEmailFromToken()` for instant synchronous nav rendering.
* **`frontend/src/routes/settings.tsx`**: Updated `clientLoader` to resolve user identity synchronously via `getUserEmailFromToken()` during route protection.
* **`frontend/src/routes/llm-settings.tsx`**: Enabled view toggles for Admin (`allowAllView={isAdmin}`) while locking normal users to Basic view (`forceHideAdvancedView={!isAdmin}`). Fixed `forgeMe.user.email`.
* **`openhands-server/openhands/app_server/user_auth/supabase_user_auth.py`**: Updated `get_user_settings()` so platform admins get OpenRouter model diffs first (`_platform_llm_diff()`), while non-admin domain-matched users get self-hosted Qwen diffs (`_selfhosted_llm_diff()`).

---

## 3. Frontend API Base URL & Defensive Schema Fixes

### API Gateway Routing Fix
* **Problem:** `openHands` axios client was defaulting `baseURL` to `window.location.host` (`localhost:3000`). Port 3000 is served by `sirv` (static SPA server), which returned `index.html` for `/api/v1/settings/agent-schema`. React crashed attempting to parse HTML as a JSON schema.
* **Fix (`frontend/src/api/open-hands-axios.ts`):** Pointed `baseURL` to `import.meta.env.VITE_API_BASE_URL || "http://localhost:8080"` (Nginx API gateway) with `withCredentials: true`.

### Defensive Schema Rendering & Caching Fixes
* **`frontend/src/utils/sdk-settings-schema.ts`**: Added defensive optional chaining (`?.`) and fallbacks (`(section?.fields ?? []).filter(...)`) to `getVisibleSettingsSections`, `getSchemaFields`, `isChoiceField`, and `isSettingsFieldVisible` to prevent `Cannot read properties of undefined (reading 'filter')` errors.
* **`frontend/src/components/features/settings/sdk-settings/sdk-section-page.tsx`**: Added array checks on `filteredSchema.sections`.
* **`frontend/src/hooks/query/use-agent-settings-schema.ts`**: Added `hasValidSections()` helper so empty or section-less `fallbackSchema` objects don't suppress API calls to `/api/v1/settings/agent-schema`. Set `staleTime: 0` and `retry: 2`.
* **`frontend/src/hooks/query/use-settings.ts`**: Unblocked settings queries in OSS mode (`app_mode === "oss"`) by removing `userIsAuthenticated` gating.
* **`frontend/src/lib/auth.ts`**: Exported `getUserEmailFromToken()` to safely decode the user's email directly from the in-memory JWT payload.

---

## 4. Strict Package Manager Policy (`npm`/`npx` -> `pnpm`)

To guarantee fast builds (~5s vs ~60s) and prevent the LLM from fumbling package managers:

### 3-Layer Enforcement Strategy
1. **System Prompt Enforcement (`agent/agent/prompts/base_system_prompt.md` & `agent/agent/prompt.py`)**:
   - Explicit instructions: *"NEVER use npm or npx... MUST strictly use pnpm"*. Verification rules updated from `npm run build` to `pnpm run build`.
2. **Auto-Scaffolding (`agent/agent/runner.py`)**:
   - Pre-scaffolds Next.js projects using `pnpm create next-app@latest . --use-pnpm --yes`.
3. **Sandbox Binary Alias Hijack (`agent/agent/runner.py`)**:
   - Inside the container/sandbox workspace, step 3.9 physically removes `npm` and `npx` binaries and symlinks them directly to `pnpm`:
     ```bash
     rm -f $(which npm) $(which npx) && ln -s $(which pnpm) /usr/local/bin/npm && ln -s $(which pnpm) /usr/local/bin/npx
     ```
   - Even if the AI model outputs `npm install` or `npx create-next-app --use-npm`, Linux executes `pnpm`!

---

## 5. Loop Prevention & Interactive Command Discipline
* **`max_iterations` Limit (`agent/agent/runner.py`)**: The OpenHands `Conversation` object is hard-limited to `max_iterations=15` to prevent infinite token burns on confused loops.
* **Interactive Command Prevention (`agent/agent/prompts/base_system_prompt.md`)**: Strict rule forcing `--yes`, `-y`, or `--non-interactive` on all scaffolding commands to prevent terminal hangs.
* **Rogue Coding Discipline (`agent/agent/prompts/base_system_prompt.md`)**: Strict error discipline rule requiring targeted single-file fixes instead of app rewrites when compilation errors occur.

---

## 6. Newly Created Files & Purpose

* **`docker-compose.dev.yml`**: Primary development multi-container compose file unifying `control-plane` (api, worker, db, cache, nginx), `openhands`, `agent`, `frontend`, `prometheus`, and `grafana`.
* **`docker-compose.prod.yml`**: Production compose configuration with production environment overrides.
* **`BLUHANDS_CONTEXT.md`**: Living documentation context file for AI agents and developers.
* **`benchmark.py` & `benchmark.ps1`**: Python and PowerShell benchmarking tools for measuring inference TPS, latency, and throughput of LLM endpoints.
* **`get_models.ps1`**: PowerShell utility for querying host endpoint model registries.
* **`schema.json`**: OpenAPI and settings schema export artifact for offline validation.

---

## 7. Git Branching Strategy
All these fixes are on branch `feature/qwen`. The workflow is to merge changes into `developement` (spelled with the extra 'e'), and then continue feature development on `feature/qwen`.
