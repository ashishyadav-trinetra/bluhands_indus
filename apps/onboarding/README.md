# Onboarding (store-creation flow) — T-A03

The merchant-facing wizard a business owner walks through after clicking
"Create your store". Collects account → business → brand → catalog → domain,
then triggers a build and shows live progress until the store is deployed.

Next.js 14 (App Router) + TypeScript + Tailwind, sharing the design-token system
with the storefront starter so onboarding and the live store feel like one product.
Shipping this also unblocks the prod nginx `frontend` upstream
(`../../control-plane/docker/nginx/nginx.conf`).

## Mock vs. live

All backend calls go through one interface (`lib/api.ts`):

- **MockApi** (default) — fully offline simulation: register, create tenant,
  domain check/purchase (entri stubbed), start build, and a deterministic build
  lifecycle (`queued → building → self_testing → deploying → live`). Lets the
  whole flow run with no control plane.
- **HttpApi** — real calls to the control plane at `/api/v1/...`. Endpoints
  already mirror the control-plane routes, so going live (T-A07) is just flipping
  env, no UI rework.

Switch with `.env.local`:

```
NEXT_PUBLIC_USE_MOCK_API=false
NEXT_PUBLIC_CONTROL_PLANE_URL=http://localhost:8000
```

## Run it

```bash
cd apps/onboarding
npm install
npm run dev        # http://localhost:3000
```

Other scripts: `npm run typecheck`, `npm run test` (Vitest), `npm run build`.

## Domain step

Three paths: free platform subdomain, bring-your-own (shows the DNS records to
add), or buy-a-new-domain (search + register). The buy/DNS-auto-config path is
stubbed here; real entri.com wiring lands in T-A04. Tip: search a domain with
"taken" in it to see the unavailable state.

## Layout

```
app/            layout, globals (tokens), page (mounts the wizard)
components/      Wizard, Stepper, ui primitives, steps/*
lib/            api (mock + http), state (reducer + context), types, utils
lib/*.test.ts   Vitest: reducer + mock API / build progression
```
