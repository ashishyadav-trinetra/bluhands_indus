# Future / To-Do

Decisions deferred deliberately — the current approach works fine, migrate when the trigger condition is met.

---

## Nango: move from cloud to self-hosted

**Current state:** Using Nango cloud (`api.nango.dev`). Secret key lives in `control-plane/.env` as `NANGO_SECRET_KEY`.

**Why migrate:** Data residency, cost at scale, or full control over OAuth redirect infrastructure.

**When to do it:** When connection volume makes Nango cloud pricing significant, or when a customer requires on-prem data handling.

**What changes (minimal):**

1. Clone and run Nango self-hosted:
   ```bash
   git clone https://github.com/NangoHQ/nango
   cd nango && docker compose up
   ```

2. Update two env vars in `control-plane/.env`:
   ```env
   NANGO_SECRET_KEY=<key-from-self-hosted-dashboard>
   NANGO_BASE_URL=https://nango.yourdomain.com
   ```

3. Pass `host` to the frontend SDK in `frontend/src/routes/connectors.tsx`:
   ```ts
   const nango = new Nango({ host: import.meta.env.VITE_NANGO_HOST });
   ```

4. For each OAuth integration (Stripe, Shopify, HubSpot, etc.) — register an OAuth app on the provider's dev console and set the redirect URI to `https://nango.yourdomain.com/oauth/callback`. Enter `client_id` / `client_secret` in the self-hosted Nango dashboard.

**No changes needed** to the session/webhook/connections route logic in `control-plane/app/routers/integrations.py`.

---
