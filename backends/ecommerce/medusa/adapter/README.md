# medusa/adapter — stable contract + tenant scoping (PLANNED, part of T-A02/T-A04)

The agent and storefront talk to **this adapter's stable contract** (the
capability manifest), never to raw Medusa internals — so we can upgrade Medusa
underneath without breaking generated apps (ADR-3).

Responsibilities (to implement):
- **Stable surface:** expose exactly the endpoints in `../capability-manifest.json`; absorb Medusa version changes here.
- **Tenant scoping:** resolve tenant → Medusa store/sales-channel + publishable key (per ADR-7). Pooled (RLS) by default; siloed instance for enterprise.
- **India/UPI:** inject the Razorpay/UPI payment provider config as a Medusa **plugin/module**, not a core fork.

For T-A02 the adapter is a thin pass-through (storefront hits Medusa directly via
the manifest); real tenant-scoping lands with T-A04 (isolation).
