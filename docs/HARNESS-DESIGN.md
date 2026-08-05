# BluHands — Harness Design

> How to make a *small, cheap* model build *robust, production* software, reliably.
> Companion to `DECOUPLING-PLAN.md` (which covers *how to swap* engines). This one
> covers *what the harness must do* regardless of which engine is underneath.
> Written 2026-08-04.

---

## 0. The reframe: your two options are the same strategy

You asked: build a BaaS so the agent writes less code, **or** make the harness
strong? They are not alternatives. They are the same principle applied at two
different layers:

> **Every line the model doesn't have to write is a line that can't be wrong.**

- **A BaaS** reduces *how much* novel code exists. It deletes whole categories
  (auth, storage, realtime, jobs, migrations) from the model's job.
- **A strong harness** constrains *how* the remaining code gets written —
  decomposition, verification, retry, memory, escalation.

You need both, and they multiply. But the ordering matters, because a strong
harness with no BaaS still ships working small apps, whereas a BaaS with a weak
harness still ships broken frontends. **Harness first.**

### Three open questions and why the plan survives them

I couldn't resolve these from the repo, and they'd normally change the answer:

1. **Do customers keep the generated app on your infra, or export and self-host?**
   (`domains.py` implies hosted; `github_push` implies exported.)
2. **Does "millions of users" mean platform-wide density, or per-app throughput?**
3. **"The continue part"** — Continue.dev the tool, or resumable/continuable builds?

The recommendation below is deliberately chosen to be **invariant** to all three:
an open-source, self-hostable BaaS works whether you host or they export; the
decomposition design gives you resumable builds for free; and the scale answer
only changes which starter tier you default to. Where a fork genuinely matters, it
is marked **[FORK]**.

---

## 1. The BaaS question — adopt, don't build. You may already own the answer.

### 1.1 You already made this decision once

`SYSTEM-DESIGN.md` §1 states the hard constraint: *the agent only builds the
frontend, wired to a pre-built, battle-tested backend.* Medusa is that backend for
e-commerce. **A BaaS is exactly that constraint, generalized from one industry to
all of them.** So your instinct is not a new idea — it is the correct
generalization of the one decision that makes the platform work at all.

### 1.2 But do not build one

A credible BaaS is auth + row-level authz + a database API + storage + realtime +
functions + migrations + an admin UI + SDKs. That is a multi-year product with a
permanent security surface, and it is not your differentiator. Your differentiator
is the harness that turns a sentence into a working app.

Rung 5 of the ladder: an already-existing dependency solves this.

### 1.3 The candidates

| Option | Per-tenant cost | Ceiling | Export-friendly | Notes |
|---|---|---|---|---|
| **PocketBase** | Very low — one Go binary + SQLite, ~30MB RSS | Modest (single-node, SQLite) | Excellent | Trivial to provision per tenant. Best economics by far. |
| **Supabase (self-hosted)** | High — ~8 containers per project | High (Postgres) | Good | You already know it. Heavy for per-tenant isolation. |
| **Appwrite** | Medium | Medium-high | Good | Batteries-included, decent admin UI. |
| **Postgres + PostgREST + a thin auth service** | Low-medium | High | Excellent | Most control, most work. Multi-tenant via RLS in one cluster. |

**Recommendation:** two tiers, not one.

- **Default tier → PocketBase.** One container per generated app, near-zero
  marginal cost, and the generated code is portable. This is what makes
  per-tenant provisioning economically sane at density.
- **Serious tier → Postgres + PostgREST (or self-hosted Supabase).** For apps that
  outgrow SQLite. The migration path is a real project, so make the tier boundary
  explicit rather than promising a seamless upgrade you haven't built.

**[FORK]** If customers export and self-host, PocketBase's single-binary story is
a genuine selling point — they can run it anywhere. If you host forever, the
Postgres tier's operational maturity matters more and you might invert the default.

### 1.4 The irony worth naming

Part B of `DECOUPLING-PLAN.md` removes Supabase. This section considers adding a
BaaS. Those are not in conflict — they are different layers:

- **Platform identity** (who is the BluHands customer) — you should own this. That
  is Part B, and it stands.
- **Generated-app substrate** (what the built app runs on) — this should be a
  BaaS, and it should not be code you maintain.

Keep them separate on purpose. Sharing one Supabase instance across both would
couple your control plane's blast radius to every generated app.

### 1.5 It needs no new architecture

`pack.json` already describes a backend: `endpoints`, `envTemplate`, `buildCmd`,
`product_shape`, `criticalFlows`. A BaaS is just another pack backend. You add
`packs/saas/` with a PocketBase manifest and the existing machinery runs it. The
decoupling work in Part A is the prerequisite, and it is the *only* prerequisite.

---

## 2. Seven levers that make a small model reliable

Ranked by impact per unit of effort. A 30–35B model fails at open-ended authoring
and succeeds at bounded transformation — every lever below converts the former
into the latter.

### Lever 1 — Transformation over generation

Never let the model start from a blank directory. A golden starter that already
typechecks, builds, has a design system, auth wired, and a passing test means the
model's job is *edit working code*, not *author a system*. You already do this for
e-commerce; make it universal — every pack ships a starter that is green on
arrival.

**Effect:** the single largest quality delta between a 35B and a frontier model
disappears, because the hard architectural decisions are already made in the
starter by a human.

### Lever 2 — Task decomposition into a verifiable DAG  ← **biggest lever**

Today one `conversation.run()` is one unbounded episode. A small model's error
rate compounds per step; a 200-step episode is a coin flip. Split it.

The planner emits a DAG. Each node:

```json
{
  "id": "T-07",
  "title": "Product detail page fetches from the API",
  "files": ["app/products/[handle]/page.tsx", "lib/api.ts"],
  "depends_on": ["T-03"],
  "acceptance": {
    "cmd": "npm run typecheck && npx playwright test tests/pdp.spec.ts",
    "expect": "exit 0"
  },
  "budget": { "steps": 12, "model": "small" }
}
```

The executor runs **one node at a time**, with only that node's context. Fail →
retry with the error text → retry at a higher model tier → mark `blocked` and move
on to independent nodes.

**Why this is the biggest lever:**
- 20 × 10-step episodes instead of 1 × 200-step. Failures are isolated and cheap
  to retry, and one bad node no longer poisons the whole build.
- Each node has a *machine-checkable* acceptance test. The model cannot declare
  victory.
- Independent nodes can run in parallel.
- **The DAG is the resumability answer.** Persist it and "continue this build
  tomorrow", "add a feature to a shipped app", and "retry the 3 failed tasks" are
  all the same code path. This resolves reading (2) of "the continue part" for free.

### Lever 3 — Machine gates, never self-report

The model does not get to say "done." A node closes when its `acceptance.cmd`
exits 0. The build closes when the pack's gate script exits 0:

```bash
# packs/<industry>/verify.sh — non-negotiable, runs in-sandbox
npm run typecheck && npm run lint && npm run build \
  && npx playwright test && node scripts/a11y-check.mjs
```

This also fixes the open-loop defect from the earlier harness review: today
`verify()`'s result is discarded and a blank page reports `success=True`.

### Lever 4 — The escalation ladder  ← **the "cheap" answer**

Do not pick one model. Pick a ladder, per node:

| Attempt | Model tier | Typical use |
|---|---|---|
| 1 | small (your 35B, self-hosted — near-zero marginal cost) | ~70–80% of nodes: CRUD pages, styling, wiring |
| 2 | small + full error output + relevant code-graph context | most remaining failures |
| 3 | mid (Sonnet-class) | genuinely hard nodes |
| 4 | large, or mark blocked and surface to a human | rare |

Because most nodes are easy, most of the build runs on the cheap model, and you
only pay frontier prices for the few nodes that earn it. This is how you get cheap
*and* effective rather than choosing. Log tier-per-node so you can see where the
money actually goes and tune the ladder from data.

### Lever 5 — Context selection via a code graph

A 35B with a 32k usable window lives or dies on retrieval. Dumping the repo is
both expensive and *worse* — irrelevant context measurably degrades small models.

Build a code graph: tree-sitter parse → symbols, imports, references → SQLite.
For a node, select context by graph proximity to `files[]` plus a ranking pass.
This is the "graph memory" that matters (see §3), and it is also the largest
single token-cost lever you have.

### Lever 6 — A tolerant tool protocol with repair-and-retry

Your last several commits patch `_extract_security_risk`, auto-fill
`TaskItem.title`, guard `security_risk` injection, and set
`confirmation_mode=False` — all because qwen3.6-35b doesn't emit the JSON schema
OpenHands assumes. That is a recurring tax, not a one-off.

Fix it at the protocol layer: a permissive parser that accepts the model's actual
output shape, repairs common malformations (missing required field, string-encoded
JSON, XML-style tags), and on unrecoverable parse failure re-prompts with the
schema and the specific error. Hermes's XML-tag protocol exists for exactly this
reason and works down to 30B-class models.

### Lever 7 — Learned skills per pack

After a successful build, have the engine write a short note — what worked, what
broke, the fix — into `packs/<industry>/learned/`. Inject the top-N on subsequent
builds of that pack. The 50th e-commerce build should be cheaper and better than
the 5th.

Of the seven levers, this is the only one that is a *moat* rather than a fix. The
others make you competent; this one makes you compound.

---

## 3. Memory — three kinds, and only one should be a graph you build

You asked about graph memory. The honest answer: **yes to a graph, but of the
code, not of the world.**

### 3.1 Code graph — build it

Tree-sitter symbol/import/reference graph in SQLite. Powers Lever 5. Proven
approach (aider's repo map, and effectively what every good coding agent does).
Cheap: one parse pass, incremental on edit. This is the highest-value memory in
the entire system and it is a graph.

### 3.2 Build episodic memory — build it, keep it small

A table of `(pack, task_kind, symptom, fix, outcome)` with embeddings. On a failing
node, retrieve the 3 nearest past failures and inject their fixes. This is Lever 7
made concrete, and it is where "remember effectively" actually pays — the agent
stops re-discovering that Next.js 15 needs `await params`.

### 3.3 Tenant semantic memory — you already have it

Brand, business, products, preferences. Structured fields on the build spec. No
vector store needed. Don't over-build this.

### 3.4 What NOT to build

**A general knowledge graph (Neo4j / Graphiti / Zep / mem0-style).** These are
built for conversational agents that need to recall facts about a user across
months. A build agent's memory needs are dominated by *code structure* and *past
failures*, both served better by §3.1 and §3.2 at a fraction of the operational
cost. Revisit only if you add a persistent per-user assistant that lives outside
builds.

---

## 4. MCP and plugins — make tools engine-independent

### 4.1 The architectural win

Speak **MCP at the tool boundary**. Then tools stop belonging to OpenHands and
start belonging to *you*, which directly reinforces the Part A engine swap — today
`FileEditorTool` and `TerminalTool` are OpenHands imports, so swapping engines
means rebuilding your toolset. Under MCP, the engine changes and the tools don't.

Expose your existing capabilities as MCP servers:

- `playwright_verify` — the self-test gate
- `code_graph` — symbol lookup, neighbours, ranked context
- `pack_seed` — industry seeding
- `baas_admin` — provision collections/tables, set auth rules
- `brand` — design-token application

Consume community servers where they're clearly better: filesystem, git, fetch,
postgres, playwright.

### 4.2 The warning nobody gives you

**Tool sprawl destroys small models.** Every additional tool widens the selection
problem, and a 35B degrades noticeably past roughly 15–20 tools — the exact regime
you're operating in. Do not "install all the MCPs."

Curate a tool set **per pack**, keep it under ~15, and treat it as a tuned
parameter. Measure selection accuracy when you add one.

### 4.3 Continue.dev

**[FORK — reading (1) of your question]** Continue's transferable idea is
**path-scoped rules auto-attached by glob**: a rule file activates only when the
model touches matching files. That maps cleanly onto per-pack rules —
`packs/saas/rules/*.md` with `globs:` frontmatter — and it is strictly better than
a single monolithic prompt, because it keeps irrelevant instructions out of a small
model's context. Worth copying. Its plugin hub is less relevant to you.

---

## 5. "Production-grade" — what actually produces it

You cannot prompt your way to production quality. Four mechanisms do the work:

1. **The starter is already production-grade.** Whatever the starter has — strict
   TypeScript, error boundaries, loading states, input validation, structured
   logging, a11y baseline — the generated app inherits for free. This is where
   most of the quality comes from. Invest here, not in prompt wording.
2. **The BaaS owns the hard parts.** Authn/z, migrations, connection pooling,
   rate limits, backups. Nobody's generated code needs to get these right.
3. **The constitution is enforced, not described.** `code_instruction.md` is ~10k
   words of prose. A 35B will not comply with 10k words of prose. Convert it into
   things that *fail the build*: `tsconfig` strict flags, an ESLint ruleset, a
   `verify.sh`. Prose the model must remember → rules the model cannot violate.
4. **Gates run in-sandbox, every node.** See Lever 3.

### On "millions of users"

**You cannot generate scalability. You can only inherit it.** No amount of model
capability makes generated application code horizontally scalable — that is a
property of the runtime, the database topology, the caching layer, and the CDN.

**[FORK]** If the target is *platform-wide density* (many tenants, modest traffic
each), PocketBase-per-tenant plus a CDN is the right and cheap answer. If a
*single generated app* must serve millions, that app does not belong on the
default tier at all — it needs the Postgres tier with pooling, read replicas, and
edge caching, and you should treat it as a distinct, priced product tier rather
than something the agent decides. Design the tier boundary explicitly; do not let
it be an emergent surprise.

---

## 6. Cost levers, ranked

1. **Context discipline via the code graph** (Lever 5) — biggest token lever;
   small precise contexts are both cheaper *and* more accurate.
2. **Escalation ladder** (Lever 4) — most nodes never touch a frontier model.
3. **Prompt caching** on the stable prefix (pack prompt + skills + rules).
4. **Step/cost caps per node** — bounds the worst case, which today is unbounded.
5. **A warm sandbox template** with `node_modules` pre-baked — you already have
   `agent/e2b/`; extend it per pack. Saves minutes of wall-clock and dollars of
   sandbox time per build.
6. **Learned skills** (Lever 7) — fewer steps to the same result, compounding.

---

## 7. Phase plan (folds into DECOUPLING-PLAN's A-phases)

| # | Work | Verify by |
|---|---|---|
| H0 | Gate script per pack + `verify()` result reaches `BuildOutcome` | Blank-page build reports `success=False` |
| H1 | Step/cost caps + `engine.resume()` fix loop (= A1–A2) | Deliberate break ⇒ 2 resume attempts, then honest failure |
| H2 | Tolerant tool-call parser + repair-and-retry | qwen build runs with **zero** SDK monkeypatches; delete the patches |
| H3 | Task DAG: planner emits nodes, executor runs one at a time | A build completes as ≥10 nodes; killing mid-build and resuming works |
| H4 | Code graph (tree-sitter + SQLite) driving node context | Median tokens/node down ≥50% at equal or better pass rate |
| H5 | Escalation ladder + per-node tier logging | Cost/build down; dashboard shows tier distribution |
| H6 | MCP tool boundary; port existing tools to MCP servers | Same pack builds under two engines with an identical tool set |
| H7 | `packs/saas/` on PocketBase — the first non-Medusa pack | A non-e-commerce app builds end-to-end, no code changes to the runner |
| H8 | Learned-skills capture + injection | Build N+20 of a pack uses fewer steps than build N |

H0–H2 are debt repayment and should not wait. H3 is the step change. H7 is the
proof that "build anything" is real.

---

## 8. What NOT to build

- **Your own BaaS.** Adopt PocketBase/Postgres. §1.2.
- **A general knowledge graph.** §3.4.
- **Your own tool protocol.** MCP exists and every ecosystem you named speaks it.
- **A fork of OpenHands.** The adapter is ~40 lines; a fork is forever.
- **A multi-agent swarm.** Fashionable and tempting, but coordination overhead is
  paid in tokens and every hand-off is a place for a small model to lose the
  thread. Multi-agent makes weak models *worse*, not better. A single agent with
  a good DAG, tight context, and real gates beats a swarm of 35Bs — revisit only
  after H3–H5 are in and you have data saying otherwise.
- **Prompt-engineering your way to quality.** Put it in the starter and the linter.

---

## 9. The one-sentence version

Build the harness so a cheap model only ever faces small, well-contexted,
machine-verifiable tasks against an already-working codebase on a backend it
doesn't have to write — then the model's weakness stops being the binding
constraint, which is the only way this is ever cheap.
