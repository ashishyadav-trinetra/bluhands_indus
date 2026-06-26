# BluHands — Current Flows (as built)

> The end-to-end flows after this session's changes. Pairs with SYSTEM-DESIGN.md
> (architecture) and STATUS-AND-ROADMAP.md (what's left).

## 1. User & auth flow (Supabase is the login)

1. User logs in with **Supabase** on the frontend → gets a Supabase JWT.
2. Every request to the control-plane carries that JWT. `get_current_user` tries
   the control-plane RS256 token first (machine/admin), then **falls back to
   verifying the Supabase JWT** (`SupabaseVerifier`).
3. **First login auto-provisions** the platform account: user + **organization** +
   owner membership + wallet (with free signup credits). This also **self-heals**:
   an existing user who somehow has no org gets one back-filled on their next
   request. → there is no manual "create account/org" step.

Roles (platform-level, set in the admin panel): `user · admin · tester · self`.

## 2. Org flow (the confusing part, clarified)

- The **Forge org** (used for builds/tenants) is **auto-created** — users never make
  it by hand. `/me` returns the user's memberships; the frontend uses
  `memberships[0].org_id`.
- The **OpenHands "Settings → LLM / select organization / SDK settings schema
  unavailable"** page is **legacy OpenHands SaaS** and is NOT used by BluHands.
  The LLM is **server-side** (agent `OPENROUTER_API_KEY` + per-role model map).
  Users should never pick an org or paste a key there → that surface should be hidden.

## 3. Access & role flow (the demo model)

- **admin / self / tester** → use the agent **for free** on the platform's LLM key.
  No per-user API key, no upgrade.
- **normal `user`** → build is blocked with **402 "UPGRADE_REQUIRED"** (must upgrade).
- **Per-role model** (control-plane → agent at dispatch): `tester → FORGE_MODEL_TESTER`
  (e.g. MiniMax), `self → FORGE_MODEL_SELF` (self-hosted Qwen), others → `FORGE_MODEL_DEFAULT`.
- **Admin panel** (`/admin/users`): list users, **change role** (incl. make-admin via
  the dropdown), **delete user** (soft-delete; can't delete self).

→ Demo flow: make a guest **admin** → they build immediately, no key, no setup.

## 4. Prompt → build flow ("prompt factoring") — now CONDITIONAL

1. User types a prompt (or clicks a starter) → frontend calls **`POST /agent/clarify`**.
2. **0 questions returned** (the common case — detailed prompts always get 0) →
   **build immediately, no dialog.**
3. **Questions returned** → the **MCQ / free-text popup** appears. Answer any/all/none,
   then **Start building** (no forced-answer gate). On confirm, the answers go to
   **`POST /agent/enhance`** which factors them into a richer `enhanced_prompt`.
4. The (possibly enhanced) prompt → **`POST /orgs/{org}/tenants/{tenant}/builds`** →
   control-plane creates a `BuildRun (queued)`, **reserves credits**, dispatches a
   Celery task.
5. **Worker** runs the FSM: `queued → provisioning → building → testing → review`,
   calling the **agent** (`/builds`) and polling it. The build page polls every 3s.
6. **Agent** runs in its **E2B sandbox** (one per build): seed/clone → build → serve
   → Playwright self-test → preview URL. On **review**, the user approves → `live`
   and **credits are captured**; on failure, **credits are auto-refunded**.

Clarify/enhance are cheap LLM calls — they use the LLM whenever a key is set, and
fall back to deterministic heuristics offline.

## 5. GitHub flow (optional, user-driven, via Nango)

- **Connect** GitHub through the existing **Nango** ConnectUI (Connectors page).
- In the build popup: pick a **repo** + toggle **"Pull latest before building"** and
  **"Push code after building"**.
- At dispatch the control-plane fetches the GitHub **token from Nango** (never
  stored) and hands it to the agent; the agent **clones/pulls** the repo as the
  workspace and/or **commits + pushes** the result — all inside the sandbox.

---

## Next up (queued)

- **Credit usage** — surface balance + cost per build; enforce/auto-refund are
  already in the ledger (reserve→capture/refund). Remaining: machine-route API-key
  auth (T-404) + a usage/credits UI + clear per-action pricing.
- **Sandbox integration plan** — E2B is wired (provider + per-build microVM + push/
  pull). Remaining: build the `bluhands-node` template, confirm OpenHands-in-sandbox
  on a real run, warm-pool / cached `node_modules` for cold-start, and a queue/
  autoscaler for many concurrent builds.
