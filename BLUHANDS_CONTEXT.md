# BluHands Repository Context

This document exists to quickly orient any future agents working on this codebase. It documents core architectural changes, constraints, role-based access control (RBAC), API routing fixes, and package management policies applied to the `bluhands_indus` OpenHands integration.

---

## 1. The Agent Architecture & Inference Engine
* **Current Model:** `qwen3.6-35b-a3b` served by **self-hosted vLLM at `http://122.160.253.37:8000/v1`**. Set via `BLUHANDS_SELFHOSTED_*` in the server `.env`, which overrides the compose defaults. Trinetra employees (`*@trinetralabs.ai` non-admin) are auto-seeded and **pinned** to this model; platform admins instead use `claude-sonnet-4.5` on OpenRouter.
* **The old Ollama DGX box (`172.16.16.40:11434`) is DECOMMISSIONED.** It is unroutable from the EC2 host. Pointing anything at it makes every agent step block until `llm.timeout` and then retry, with nothing logged — which presents as the agent hanging on step 0, not as a network error. Do not reintroduce it.
* **Measured throughput:** ~31-33 tok/s decode; prefill ~3.5s at 13k tokens, ~16s at 52k. At or above ~25 tok/s is healthy.
* **Step budget — `LLM_MAX_OUTPUT_TOKENS` and `LLM_TIMEOUT` are COUPLED.** The cap is really a time budget (`tokens / tok-per-sec` must fit inside the timeout) while also being large enough for the agent to write a whole file in one tool call. Both failure modes have been hit in production:
  - Too **high** (was 64000, then 16000): at 32 tok/s a step needs 500s-33min but the timeout was 300s, so every step hit `litellm.Timeout` and was retried 5x. The agent never left step 0.
  - Too **low** (4096): qwen spends the budget on reasoning and the tool call is truncated mid-JSON, giving `Unterminated string ... unparseable JSON`.
  - Working values: **8192 / 900**. Measured: `finish=tool_calls`, ~186-244s per step, arguments parse cleanly.
* **Where it is enforced:** `_configure_llm()` in `live_status_app_conversation_service.py` is the choke point — it rebuilds the `LLM` object per conversation and silently drops any field it does not explicitly pass. Per-user values come from `_SELFHOSTED_STEP_CAPS` in `user_auth/supabase_user_auth.py` (`max_output_tokens`, `timeout`, `reasoning_effort=low`, `enable_thinking=False` via `chat_template_kwargs`, `max_input_tokens`). Caps are re-applied in memory on **every** settings read, because users seeded before the caps existed never re-trigger the seed. Gating is by **endpoint** (`base_url`), not by email.
* **If the agent hangs, do NOT reflexively restart vLLM.** That advice used to live here and it is wrong — the box benchmarked healthy at 31-33 tok/s throughout a multi-day outage. Check in order:
  1. **Is the endpoint reachable from the container?** Run `curl -s -m 20 -o /dev/null -w '%{http_code}' <base_url>/models` inside the `openhands` container. A hang here (rather than a status code) is the whole bug.
  2. **Do the cap and timeout still fit each other?** (see above)
  3. **Benchmark it:** `python benchmark.py` (reads endpoint + key from the environment).
* **Agent Flow:** We use OpenHands' default `CodeActAgent` architecture. It relies on a linear ReAct loop inside the sandbox.

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
   - Backend auto-seeds their settings with the self-hosted Qwen model (`openai/qwen3.6-35b-a3b` on the vLLM box `http://122.160.253.37:8000/v1`), so no API key or configuration is required. The model is **pinned**: it is re-applied on every settings read, so it cannot be changed even via the API.
   - The old Ollama DGX box (`172.16.16.40:11434`) is **decommissioned**. It is unroutable from the EC2 host, and pointing anything at it makes every agent step block until `llm.timeout` and then retry — which looks like the agent hanging on step 0, not like a network error.

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
