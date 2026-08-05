# BluHands — Decoupling Plan

> Two migrations, planned together because they share nothing and can run in parallel.
> A. Detach the harness from OpenHands, so engine × industry × sandbox are all swappable.
> B. Remove Supabase, own identity end-to-end.
> Written 2026-08-04. Pairs with `SYSTEM-DESIGN.md` and `STATUS-AND-ROADMAP.md`.

---

## 0. Two findings that shrink the work

**Finding 1 — the OpenHands coupling is already tiny.** Grepped the whole agent
package. Every import of `openhands.*` lives in exactly two files:

| File | Lines | What it imports |
|---|---|---|
| `agent/llm.py` | 50, 80 | `openhands.sdk.LLM` |
| `agent/runner.py` | 375–377 | `Agent`, `Conversation`, `Tool`, `FileEditorTool`, `TerminalTool` |

`sandbox.py`, `prompt.py`, `brand.py`, `pipeline.py`, `manifests/`, `skills/`,
`seeders/`, `tools/playwright_verify.py` contain **zero** OpenHands references.
The engine swap is a one-file interface plus an adapter — days, not a rewrite.

The real coupling is not to OpenHands. It is that **the build recipe is hardcoded
inside `OpenHandsRunner._run_in_session`** — a 6-step npm/Next.js pipeline with
e-commerce assumptions baked into control flow. That is what blocks "build
anything."

**Finding 2 — in-house auth already exists and is complete.** `control-plane`
already ships: `PasswordHasher` (argon2), `TokenManager` (RS256 access +
refresh rotation), `RedisTokenBlocklist`, `User` model with `password_hash`, and
live routes for `register` / `login` / `refresh` / `logout` / `me`.
Supabase is the **fallback branch** in `get_current_user`, not the foundation.

So "build auth from scratch" is the wrong frame. It is ~85% deletion and ~15%
addition (OAuth, email verification, password reset, client-side session).
Do not rebuild what is already there and tested.

---

# Part A — Detaching the harness

## A.1 Target shape

Three independent axes. Today only the third is swappable.

```
        ENGINE                 PACK                    SANDBOX
   how the LLM drives      what to build           where it runs
   ──────────────────      ─────────────           ─────────────
   OpenHandsEngine         ecommerce               LocalSandbox   ← done
   OpenCodeEngine          crm                     E2BSandbox     ← done
   ClaudeAgentEngine       saas                    (Firecracker…)
   RawLoopEngine           internal-tool
```

The runner becomes a thin, generic orchestrator over the three. Nothing in it
knows about npm, Next.js, Medusa, or OpenHands.

## A.2 The engine interface

New file `agent/agent/engines/base.py`. This is the whole abstraction:

```python
@dataclass(frozen=True)
class EngineRequest:
    prompt: str
    workdir: str
    model: str
    max_steps: int = 60          # hard cap — today there is none
    max_cost_usd: float | None = None
    tools: list[str] = ()        # logical: "terminal", "file_edit", "browser"

@dataclass(frozen=True)
class EngineResult:
    ok: bool
    detail: str
    steps: int = 0
    cost_usd: float | None = None

class CodingEngine(Protocol):
    name: str
    async def start(self, req: EngineRequest, session: SandboxSession,
                    on_event: Callable[[dict], None] | None = None) -> EngineResult: ...
    async def resume(self, feedback: str) -> EngineResult: ...
    async def close(self) -> None: ...
```

`resume()` is the load-bearing method. It is what turns the verify step from a
discarded screenshot into a real fix loop, and OpenHands already supports it
natively (`conversation.send_message(...)` then `conversation.run()` again).

`engines/openhands_engine.py` is a near-literal lift of the existing
`_customize_in_session` body — including the E2B sandbox reuse and the
`confirmation_mode=False` workaround, which stays engine-local instead of
polluting the runner.

## A.3 The industry pack

Collapse four scattered per-industry registries (`manifests/`, `skills/`,
`seeders/`, starter path) into one directory per industry:

```
packs/
  ecommerce/
    pack.json        # manifest: envTemplate, buildCmd, serveCmd, port, endpoints,
                     #           product_shape, criticalFlows, features
    prompt.md        # base system prompt for this industry
    skills/*.md      # shadcn.md, medusa.md, ecommerce.md
    seed.py          # optional: async def seed(**kwargs)
    verify.py        # optional: async def verify(page, flow) -> list[str]
    starter/         # or a symlink/path ref to apps/starters/ecommerce-next
  crm/
    pack.json
    prompt.md
    skills/*.md
```

`packs/__init__.py` exposes `load_pack(industry) -> Pack`. Adding an industry
becomes "add a folder" — no Python edit, no registry entry, no runner change.
That is the actual test of whether the decoupling worked.

Critically, `pack.json` must grow **`steps`** (per-industry step budget) and
**`verifyFlows`** with real assertions, not just names.

## A.4 The generic runner

`runner.py` shrinks to roughly:

```
pack    = load_pack(spec.industry)
engine  = get_engine(settings, spec.engine)         # new: per-build engine choice
session = await provider.acquire(spec.build_id)

1. pack.seed(...)                    if present
2. upload pack.starter + env from pack.envTemplate  if present
3. brand tokens                      if spec.brand
4. engine.start(prompt, session)     ← was step 4, now provider-agnostic
5. run pack.buildCmd; start pack.serveCmd; WAIT FOR PORT READY
6. result = verify(preview_url, pack.verifyFlows)
   while not result.passed and attempts < pack.max_fix_attempts:
       await engine.resume(result.summary())
       rebuild + reserve + re-verify
7. push to git if requested
```

Steps 1–3 and 7 are already provider-agnostic. Step 5's readiness poll and step
6's loop are the two genuinely new pieces, and they are the ones that fix the
open-loop problem from the harness review.

## A.5 Phases

| # | Work | Verify by |
|---|---|---|
| A0 | Add `engines/base.py` + `OpenHandsEngine` (lift, no behaviour change) | Existing `test_runner.py` still green; one live build identical to today |
| A1 | Add readiness poll before verify; make `_self_test` **return** its result into `BuildOutcome` | Unit test: unreachable preview ⇒ `success=False`, not silent pass |
| A2 | Add the `resume()` fix loop, capped at 2 attempts | Force a deliberate build break; assert 2 resume calls then failure reported |
| A3 | Build the `packs/` loader; port `ecommerce` into it; delete `manifests/`, `skills/`, `seeders/` | `load_pack("ecommerce")` output equals the old three loaders' output |
| A4 | Generic runner over Pack × Engine; drop e-commerce control flow | A second pack (`saas`, no backend, no seed) builds end-to-end |
| A5 | Second engine adapter (OpenCode or Claude Agent SDK) | Same pack builds under both engines |

A0–A2 are worth doing even if you never add a second engine — they are the
missing feedback loop. A3–A4 are what unlock "build anything." A5 is optional
and should wait until a real engine complaint forces it.

## A.6 What NOT to build

- No plugin/entry-point discovery system for packs — a folder scan is enough.
- No abstract "Backend" class hierarchy. `pack.json` is data; keep it data.
- Do not fork OpenHands. The adapter is ~40 lines; a fork is forever.

---

# Part B — Removing Supabase

## B.1 Exact surface

**Backend (5 real files):** `core/supabase_auth.py` (the whole verifier),
`services/auth_service.py::provision_from_supabase`,
`api/v1/dependencies/auth.py::_resolve_supabase_user` + the fallback branch,
`api/v1/dependencies/providers.py::get_supabase_verifier`, config keys.
Plus `tests/unit/test_supabase_auth.py`, `test_provision_supabase.py`.

**Frontend (6 files):** `lib/supabase.ts`, `components/features/auth/supabase-login.tsx`,
`routes/login.tsx`, `routes/root-layout.tsx`, `api/bluhands-service/forge-axios.ts`,
`api/open-hands-axios.ts`. Plus `@supabase/supabase-js` in `package.json`.

**Capabilities actually used:** email+password signup/signin, Google OAuth,
GitHub OAuth, client session storage with silent refresh. Nothing else — no
Supabase storage, no realtime, no RLS, no edge functions. That is a small
replacement surface.

## B.2 What must be built (the only genuinely new code)

1. **OAuth 2.0 / OIDC authorization-code flow with PKCE** for Google and GitHub.
   Use a maintained library (`authlib`) — this is a trust boundary, do not
   hand-roll the state/nonce/PKCE handling.
2. **Email verification** — signed, single-use, expiring token + a transactional
   email provider (Resend/SES/Postmark). Blocks nothing else; can ship after cutover.
3. **Password reset** — same token machinery, plus mandatory invalidation of all
   refresh tokens on reset.
4. **Client session layer** — replace `getAccessToken()` with an `AuthProvider`
   that holds the access token **in memory**, keeps the refresh token in an
   `HttpOnly; Secure; SameSite=Lax` cookie, and silently refreshes on 401.
   Do not copy Supabase's localStorage model; you can do better because you own
   the server.
5. **Rate limiting + lockout** on `/login`, `/register`, `/reset` — Supabase gave
   you this for free and its absence is easy to miss.

Everything else — hashing, JWT issuance, rotation, revocation, RBAC, JIT org
provisioning — already exists and gets reused as-is.

## B.3 The password migration (the real risk)

Supabase Cloud gives direct Postgres access, so `auth.users.encrypted_password`
(bcrypt) is exportable alongside `id`, `email`, `email_confirmed_at`,
`raw_user_meta_data`. Your `PasswordHasher` is argon2 and will not verify bcrypt.

**Recommended:** import the bcrypt hashes verbatim, teach `PasswordHasher.verify`
to detect a `$2a/$2b/$2y$` prefix and verify via bcrypt, then **rehash to argon2
on successful login** (the `needs_rehash` hook already exists in `security.py`).
Users notice nothing; the bcrypt path drains itself and can be deleted in a
release or two.

**Fallback if hash export is blocked:** forced password reset by email at
cutover. Works, but expect meaningful user drop-off — treat it as plan B.

OAuth-only users have no password at all; match them on `email` and re-link
`external_id` to your own provider subject on first login.

## B.4 Phases

| # | Work | Verify by |
|---|---|---|
| B0 | Export `auth.users`; confirm hashes are readable; count password vs OAuth-only users | Row counts reconciled against the Supabase dashboard |
| B1 | bcrypt-verify + rehash-on-login in `PasswordHasher` | Unit test: bcrypt hash logs in, row is argon2 afterwards |
| B2 | OAuth (Google, GitHub) authorization-code + PKCE endpoints on forge | Manual round trip both providers; state/PKCE mismatch is rejected |
| B3 | Email verification + password reset + rate limiting | Tests for expiry, single-use, and refresh-token invalidation on reset |
| B4 | Frontend `AuthProvider`; both axios clients read from it; login page rewritten | Login, refresh-on-401, and logout work with Supabase env vars **unset** |
| B5 | Import users into `users`; run both auth paths in parallel behind a flag | Every migrated user authenticates natively in staging |
| B6 | Flip the flag; monitor 401 rate for one week | 401 rate flat vs baseline |
| B7 | Delete `supabase_auth.py`, `provision_from_supabase`, the fallback branch, `lib/supabase.ts`, the dependency, and all `SUPABASE_*` env keys | `grep -ri supabase` returns only this document |

Keep B5's dual-run. It is the entire safety net, and it is cheap because
`get_current_user` is *already* structured as try-native-then-fallback.

## B.5 Honest cost

You are taking on: credential storage liability, OAuth app registration and
secret rotation for every provider, email deliverability, breach response, and
the ongoing "reset password" support load Supabase absorbed for you. The code is
maybe two weeks. The operational ownership is permanent. That is a real trade —
worth it for control and data residency, not worth it to save the subscription.

---

# Part C — What OpenCode and Hermes do better

Verified against current sources (Aug 2026), scoped to what is *stealable*.

## C.1 OpenCode

**1. The harness is a protocol, not a library.** OpenCode runs as a local HTTP
server with an OpenAPI spec; the TUI, the VS Code extension, and the desktop app
are all just clients. That boundary is precisely the one Part A is trying to
draw. If you adopt one idea, adopt this: define the engine as an API surface, not
a Python import. It makes engine swaps a config change and gives your frontend a
real streaming contract instead of the current OpenHands-specific WebSocket.

**2. Agents are markdown files with frontmatter.** `.opencode/agents/*.md` —
filename is the identifier, frontmatter carries `model`, `permission`, and
`steps`, body is the system prompt. Your `skills/*.md` + `_INDUSTRY_SKILLS` dict
is a weaker version of this. Adopt the frontmatter format for `packs/*/prompt.md`
and per-industry model/step config comes free.

**3. A permission ruleset per agent, resolved by deep merge.** Hardcoded safety
defaults (`*.env` requires ask) → agent defaults → user config. Your build agent
currently has unrestricted terminal access inside a sandbox with a live GitHub
token in the remote URL. A deny/ask ruleset is the cheapest hardening available.

**4. `steps` as a first-class cap, and compaction as a hidden system agent.**
Your `conversation.run()` has no step, cost, or time bound. OpenCode treats the
budget as config and context compaction as a dedicated internal agent. Both are
straight fixes for problems you already have.

**5. A provider layer over 75+ backends** instead of your two hardcoded paths
plus a WAF user-agent monkeypatch.

## C.2 Hermes (Nous Research)

**1. Skills are learned, not authored.** Hermes's differentiator is a built-in
learning loop: it writes its own skills from experience and reuses them, so the
same task gets faster and cheaper on repeat. Your `skills/*.md` are static files
a human maintains. The pragmatic middle path for you: after a successful build,
have the engine emit a short "what worked for this stack" note into a per-pack
`learned/` directory, and inject the top-N on subsequent builds of the same pack.
That is a weekend of work and it compounds — a platform that gets better at
`shopify-clone` the 50th time is a moat that OpenHands does not give you.

**2. Tool-calling that survives small models.** Hermes uses an explicit
XML-tagged protocol (`<tools>`, `<tool_call>`, `<tool_response>`) rather than
relying on provider-native function-calling JSON, and it is specifically built to
work with ~30B-class local models without constant framework debugging. Look at
your last five commits: `_extract_security_risk` patched, `TaskItem.title`
auto-filled, `security_risk` injection guarded, `confirmation_mode=False` to dodge
a validation error — all of it because `qwen3.6-35b-a3b` does not emit the JSON
schema OpenHands assumes. **Hermes solves the exact problem you are patching
around.** If you plan to keep serving a self-hosted 35B from `api.bluehands.ai`,
a Hermes-style text protocol with a repair-and-retry parser will delete that
entire class of bug.

**3. Persistent per-user model across sessions**, where you write a
`conversation.json` summary with an empty `steps: []` array.

## C.3 What OpenHands still does better

Real sandbox/runtime lifecycle management, a mature event-stream protocol your
frontend already speaks, and per-conversation agent-server isolation. Do not
throw that away.

## C.4 Recommendation

Do not swap engines. Steal four things, in this order:

1. **Step/cost caps + the verify→resume loop** (from OpenCode's `steps`) — fixes
   your worst harness defect and is required for A2 anyway.
2. **Markdown-with-frontmatter agent/pack definitions** (from OpenCode) — makes
   A3 config-driven instead of code-driven.
3. **A tolerant tool-call parser with repair-and-retry** (from Hermes) — deletes
   the qwen monkeypatch class permanently.
4. **A per-pack learned-skills directory** (from Hermes) — the only one of the
   four that is a durable competitive advantage rather than a fix.

Items 1–3 are debt repayment. Item 4 is the product.

---

## Sources

- [Agent System | sst/opencode | DeepWiki](https://deepwiki.com/sst/opencode/3.2-agent-system)
- [Inside OpenCode: Understanding the Architecture Behind the AI Runtime](https://falexm.medium.com/inside-opencode-understanding-the-architecture-behind-the-ai-runtime-01236d9370ff)
- [Session Management | sst/opencode | DeepWiki](https://deepwiki.com/sst/opencode/2.1-session-management)
- [Hermes Agent Documentation | Nous Research](https://hermes-agent.nousresearch.com/docs/)
- [Hermes 3 Technical Report (arXiv)](https://arxiv.org/pdf/2408.11857)
- [Hermes Agent by Nous Research, Explained](https://aiengineerinsights.com/blog/hermes-agent-nous-research-guide/)
