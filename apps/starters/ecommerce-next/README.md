# ecommerce-next — golden storefront starter (T-A05)

A real, runnable Next.js (App Router) + Tailwind + shadcn-style storefront. This
is the scaffold the **BluHands agent edits** rather than generating UI from
scratch — our biggest lever on quality, consistency, and token cost (ADR-4).

## What the agent does with it
1. Copies this starter into the build workspace.
2. Sets `NEXT_PUBLIC_MEDUSA_URL` / publishable key from the tenant's capability manifest.
3. Wires real flows (filters, product detail, cart, checkout) against the Medusa Store API via `lib/medusa.ts`.
4. Applies the merchant brand kit by editing the **design tokens** in `app/globals.css` (never by rewriting component styles).
5. Runs the Playwright self-test (the agent's verify tool) before deploy.

## Layout
- `app/` — routes (`page.tsx` = storefront home; server component fetching products).
- `components/ui/` — shadcn primitives (`button`, `card`).
- `components/` — `product-card`, `product-grid`, `filters`.
- `lib/medusa.ts` — typed Store API client; `mapProduct` is a **pure, unit-tested** normalizer.
- `lib/utils.ts` — `cn` + `formatPrice`.

## Run locally
```bash
npm install
cp .env.example .env.local   # point at a running Medusa
npm run dev                  # http://localhost:3000
npm test                     # vitest (pure logic: mapProduct)
npm run typecheck
```

## Conventions
- Edit **design tokens**, not component internals, to re-theme.
- Keep `lib/` pure where possible so it stays unit-testable.
- The UI degrades gracefully if Medusa is unreachable (home shows a friendly message).
