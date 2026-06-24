# ecommerce / medusa — golden backend (T-A02)

Medusa v2 = the pre-built e-commerce backend the agent's storefront talks to.
This folder holds the **golden runtime config** (compose + Dockerfile + env +
capability manifest + adapter). The Medusa **app source** is generated once by
`create-medusa-app` into `./app/` and is git-ignored (huge, scaffolder-owned).

## One-time: scaffold the Medusa app (needs Node 20 + network)

```bash
cd catalog/ecommerce/medusa
# Creates the Medusa v2 project in ./app (skip its bundled DB prompt; we use compose).
npx create-medusa-app@latest app --skip-db --no-browser
cp .env.example .env
```
Point the generated `app/medusa-config.*` at the env vars in `.env`
(`DATABASE_URL`, `REDIS_URL`, `*_CORS`, `JWT_SECRET`, `COOKIE_SECRET`).

## Boot it (Docker)

```bash
docker compose up --build
# Postgres on host :5444, Redis on :6390, Medusa API on :9000
```
The `medusa` container installs deps (first run), runs `medusa db:migrate`, then
`npm run dev`.

## Seed + create a publishable key (so the storefront can read products)

```bash
# seed demo products (create-medusa-app ships a seed script):
docker compose exec medusa npm run seed
# create an admin user:
docker compose exec medusa npx medusa user -e admin@medusa.local -p supersecret
# then in Admin (http://localhost:9000/app) create a Publishable API Key,
# or via script, and put it in the storefront's NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY.
```

## Verify (this is the T-A02 acceptance check)

```bash
curl -s -H "x-publishable-api-key: <KEY>" \
  "http://localhost:9000/store/products?limit=2" | head
```
You should get JSON with a `products` array whose items match
`capability-manifest.json` → the same shape `apps/starters/ecommerce-next/lib/medusa.ts`
expects. Then run the storefront pointing `NEXT_PUBLIC_MEDUSA_URL=http://localhost:9000`
and it renders the product grid.

## Notes
- India/UPI (Razorpay) is added as a **Medusa plugin/module** + env config, NOT a fork of Medusa core (ADR-3).
- Versions move fast — match commands to whatever `create-medusa-app` installs; adjust the Dockerfile CMD if the generated `package.json` scripts differ.
- `./app/` and `.env` are git-ignored (see `.gitignore`).
