# Multi-tenancy — make each login its own user

**The bug:** the app-server ran `DefaultUserAuth`, whose `get_user_id()` always
returns `None`. So every login collapsed to one global user — shared
conversations, settings, GitHub identity (`ashish-yadav-911`), and model.

**The fix (this change):** turn on `SupabaseUserAuth`, which reads the real
user_id (`sub`) from the Supabase JWT and keys every store per user. Conversations
already scope by `created_by_user_id` once the user_id is real.

## What's already done in the repo
1. **ES256 verification** — `supabase_user_auth.py` now verifies **both** HS256
   (shared secret) and **ES256/RS256 via JWKS** (your project signs ES256). The
   original code was HS256-only, so it silently failed and fell back to the
   single `default` user. This was the keystone.
2. **Compose env wiring** — the `openhands` service now reads `SUPABASE_URL`,
   `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_JWKS_URL`,
   `SUPABASE_JWT_SECRET`. Setting `SUPABASE_URL` is the master switch.

## What you must do on the server (can't be done from the repo)

### 1. Set the env values (server `.env` that compose reads)
```bash
SUPABASE_URL=https://xkpeexoheupmvmyhiuyv.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role key from Supabase → Settings → API>
# VITE_SUPABASE_ANON_KEY is already set (reused as the REST fallback key).
# Optional — JWKS is auto-derived from SUPABASE_URL, but you can pin it:
SUPABASE_JWKS_URL=https://xkpeexoheupmvmyhiuyv.supabase.co/auth/v1/.well-known/jwks.json
```
The **service_role** key is required — the per-user settings/secrets stores write
via the Supabase REST API and need it to bypass RLS.

### 2. Create the two tables in Supabase (SQL editor)
The settings/secrets stores use these exact tables (REST/PostgREST — they are NOT
auto-created):
```sql
create table if not exists public.user_settings (
  user_id    text primary key,
  settings_json jsonb,
  updated_at timestamptz not null default now()
);
create table if not exists public.user_secrets (
  user_id    text primary key,
  secrets_json jsonb,
  updated_at timestamptz not null default now()
);
-- Server-side access uses the service_role key (bypasses RLS), so no policies
-- are strictly required. If you enable RLS, add service_role policies.
```

### 3. Deploy
```bash
cd ~/var/www/bluhands_indus && git pull
docker compose build openhands && docker compose up -d openhands
docker compose logs -f openhands   # watch for auth errors on first requests
```

### 4. Re-seed the default model PER USER (optional, recommended)
The global model seed no longer applies (settings are per-user now). Either:
- seed each user after first login with the same `POST /api/v1/settings` call
  (now scoped to that user when their token is attached), or
- leave it and let each user pick a model — but then the LLM popup may reappear
  for new users (it triggers on `GET /settings == 404`).

## Verify it works
Log in with **two different Google accounts**. Each must see:
- an **empty, distinct** conversation list (not your chats),
- its **own** settings (not your model), and
- **no** GitHub connection (not `ashish-yadav-911`).

If a second user still sees your data, check `docker compose logs openhands` for
"Invalid Supabase token" (verification failing → falling back to `default`) — that
means the ES256/JWKS path isn't resolving (wrong `SUPABASE_URL`/JWKS) and every
user is still collapsing to one.

## Notes
- forge still owns auth/billing/roles/admin; this only adds per-user **identity +
  data isolation** to the app-server. No duplication.
- Existing test conversations (stored under the old `None`/`default` user) won't
  belong to anyone after the switch — they're throwaway.
- This is the Supabase/SAAS path deferred when we chose "OSS app-server only."
  Multi-tenancy fundamentally requires it.
