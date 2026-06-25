# BluHands Production Deployment — Known Issues & Fixes

Every issue encountered deploying to `app.bluehands.ai` (EC2), in the order they appear.
Use this as a checklist on future deploys.

---

## 1. FastAPI 204 AssertionError on DELETE /builds

**Symptom:** API container unhealthy. Logs show:
```
AssertionError: Status code 204 must not have a response body
```

**Cause:** FastAPI raises this when a 204 route returns a dict/body.

**Fix:** Change the DELETE route in `control-plane/app/api/v1/routes/builds.py` to return 200:
```python
@router.delete("/{build_id}", status_code=status.HTTP_200_OK)
```
Already committed to git.

---

## 2. Docker build cache not refreshing

**Symptom:** `docker compose build --no-cache api` completes in 0.0s (uses cached manifest).

**Cause:** Docker layer cache is aggressive; `--no-cache` doesn't always force a full rebuild.

**Fix:** The api container mounts `./app` as a bind volume and runs `uvicorn --reload`.
Patch the file directly on the host — uvicorn picks it up without a rebuild:
```bash
# Edit the file on the host; uvicorn auto-reloads inside the container
nano ~/var/www/bluhands_indus/control-plane/app/api/v1/routes/builds.py
```

---

## 3. Old nginx config (`blu-hands`) conflicts with new one

**Symptom:** nginx serves the old OpenHands app even after deploying new stack.
`/etc/nginx/sites-enabled/` had two configs matching `app.bluehands.ai`.

**Cause:** Previous deployment left `/etc/nginx/sites-available/blu-hands` (with a dash)
proxying everything to port 3000 (old OpenHands).

**Fix:**
```bash
sudo rm /etc/nginx/sites-enabled/blu-hands
sudo rm /etc/nginx/sites-available/blu-hands
# Recreate correct config at /etc/nginx/sites-available/bluhands (no dash)
sudo nginx -t && sudo nginx -s reload
```

**Correct nginx config** (see `/etc/nginx/sites-available/bluhands`):
```nginx
location /forge/ {
    proxy_pass http://127.0.0.1:8001/;   # control-plane API
}
location / {
    proxy_pass http://127.0.0.1:3300;    # new frontend container
}
```

---

## 4. Cloudflare CDN serving old cached content

**Symptom:** `curl https://app.bluehands.ai` returns old OpenHands HTML even after
nginx is fixed. `curl -I` shows `server: cloudflare`.

**Fix:** Cloudflare dashboard → Caching → Purge Everything.
Do this after every frontend rebuild.

---

## 5. Old OpenHands process still running on port 3000

**Symptom:** `curl http://localhost:3000` returns OpenHands HTML.
The old app in `~/bucket/bluhands` is still running as a host process.

**Fix:**
```bash
sudo fuser 3000/tcp          # find PID
sudo kill <PID>
```

The new frontend runs on port 3300 (Docker), so nginx must proxy to 3300, not 3000.

---

## 6. `control-plane/.env.development` incomplete on server

**Symptom:** API starts but DB/Redis/Supabase connections fail.

**Cause:** The git-tracked `.env.development` is a template with blank secrets.
The server needs real values filled in.

**Required values to set manually on the server after `git pull`:**
```bash
FORGE_SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...   # from Supabase → Settings → API
# (see section 8 for JWT secret — do NOT set FORGE_SUPABASE_JWT_SECRET)
```

Use Python to write values with special characters (avoid sed — `/` breaks it):
```bash
python3 -c "
import re
key = 'YOUR_KEY_HERE'
path = 'control-plane/.env.development'
text = open(path).read()
text = re.sub(r'^FORGE_SUPABASE_SERVICE_ROLE_KEY=.*', f'FORGE_SUPABASE_SERVICE_ROLE_KEY={key}', text, flags=re.MULTILINE)
open(path, 'w').write(text)
"
```

---

## 7. VITE_SUPABASE_ANON_KEY truncated (missing JWT signature)

**Symptom:** Supabase client in browser can't authenticate. Token in localStorage exists
but `supabase.auth.getSession()` returns null.

**Cause:** The anon key in `root .env` was missing the third JWT segment (after second `.`).
A truncated key is not a valid JWT.

**Fix:** Copy the full key from Supabase → Settings → API → `anon public` key.
It must end in `.<signature>` (three dot-separated segments total).
After fixing, rebuild the frontend (VITE vars are baked at build time):
```bash
docker compose build --no-cache frontend
docker compose up -d frontend
```

Then purge Cloudflare cache.

---

## 8. 401 "Missing Authorization header" — Supabase token not sent

**Symptom:** All `/forge/api/v1/*` requests return 401. Browser Network tab shows
no `Authorization` header on requests.

**Cause:** `forge-axios.ts` interceptor calls `getAccessToken()` → `supabase.auth.getSession()`.
If the `supabase` JS client is null (wrong/empty VITE vars baked into bundle), it returns null
and no header is set.

**Fix:** Ensure `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` are set in root `.env`
before building the frontend. Rebuild after any `.env` change.

---

## 9. 401 "Invalid Supabase token" — ES256 vs HS256 algorithm mismatch

**Symptom:** Authorization header IS sent, but API returns:
```json
{"error": {"code": "UNAUTHENTICATED", "message": "Invalid Supabase token"}}
```
Direct test confirms: `FAIL: InvalidAlgorithmError The specified alg value is not allowed`

**Cause:** Newer Supabase projects sign JWTs with **ES256** (asymmetric ECDSA), not HS256.
The control-plane verifier was configured to use `FORGE_SUPABASE_JWT_SECRET` (HS256 only).
The token header shows `"alg": "ES256"`, which the HS256 path rejects immediately.

**Fix:** Switch to JWKS verification in `control-plane/.env.development`:
```bash
# Remove or comment out:
# FORGE_SUPABASE_JWT_SECRET=...

# Add:
FORGE_SUPABASE_JWKS_URL=https://xkpeexoheupmvmyhiuyv.supabase.co/auth/v1/.well-known/jwks.json
```
Already committed to git. The JWKS endpoint auto-serves the public key — no manual copy-paste.

After updating the file: `docker compose restart api`

---

## 10. `git pull` blocked by server-side env file changes

**Symptom:**
```
error: Your local changes to the following files would be overwritten by merge:
    control-plane/.env.development
```

**Cause:** The server's `.env.development` has real secrets; git version is a template.
They diverge every deployment.

**Fix workflow:**
```bash
# 1. Save any secret values you need
grep "SERVICE_ROLE_KEY\|JWT_SECRET" control-plane/.env.development

# 2. Discard local changes to conflicting files
git checkout -- control-plane/.env.development control-plane/app/api/v1/routes/builds.py

# 3. Pull
git pull

# 4. Re-add secrets using Python (not sed — slashes break sed):
python3 -c "
import re, pathlib
p = pathlib.Path('control-plane/.env.development')
t = p.read_text()
t = re.sub(r'^FORGE_SUPABASE_SERVICE_ROLE_KEY=.*', 'FORGE_SUPABASE_SERVICE_ROLE_KEY=YOUR_KEY', t, flags=re.MULTILINE)
p.write_text(t)
"

# 5. Restart — use `up -d`, NOT `restart`
# `docker compose restart` keeps the OLD env from container creation.
# `docker compose up -d` re-reads env_file and applies new values.
docker compose up -d api
```

---

## Deployment Checklist (run in order)

```
[ ] git pull (handle conflicts per issue #10)
[ ] Fill secrets in control-plane/.env.development (per issues #6, #9)
[ ] Check root .env has full VITE_SUPABASE_ANON_KEY (per issue #7)
[ ] docker compose up -d (NOT restart — restart doesn't re-read env_file)
[ ] Run DB migrations: docker compose exec api alembic upgrade head
[ ] Seed admin: docker compose exec api python3 scripts/seed_admin.py
[ ] Kill old port 3000 process if running (per issue #5)
[ ] sudo nginx -t && sudo nginx -s reload
[ ] Purge Cloudflare cache
[ ] Test: curl http://localhost:8001/api/v1/health/live
[ ] Test auth: curl with a fresh token from browser localStorage
```
