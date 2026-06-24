"""Compose the agent's build prompt from structured context (pure, testable).

The agent never guesses the backend — it's handed the capability manifest, the
brand kit, and the requested feature flags. This builds the instruction text the
OpenHands agent runs against the golden starter.
"""

from __future__ import annotations

from typing import Any

_DEFAULT_BASE = (
    "You are BluHands, an expert software engineer. You are working INSIDE a "
    "project workspace. Your job: build a production-quality app from the spec "
    "below — make it genuinely useful, not a toy.\n\n"
    "Principles:\n"
    "- Read the workspace first to understand what already exists.\n"
    "- Make only the changes the spec requires; preserve existing code that works.\n"
    "- Never hardcode data that should come from an API or database.\n"
    "- Verify with the build command (if available) and fix all errors before "
    "stopping. Keep iterating until the build passes.\n"
    "- Leave the project in a deployable, clean state."
)

_ECOMMERCE_BASE = (
    "You are BluHands, an expert e-commerce storefront builder. You are working "
    "INSIDE a Next.js (App Router) + Tailwind + shadcn project already in your "
    "workspace (the golden starter). Your job: turn it into a beautiful, "
    "production-quality, fully interactive storefront for THIS specific merchant, "
    "wired to their live Medusa backend.\n\n"
    "Division of responsibility (important):\n"
    "- FRONTEND is entirely yours: layout, design, navigation, product grid, "
    "product detail pages, category pages, cart UI, checkout UI, responsiveness, "
    "polish. Make it genuinely attractive and on-brand — not the stock template.\n"
    "- BACKEND is Medusa's: you NEVER implement cart/checkout/inventory logic "
    "yourself. For every shopper action (browse, view, add-to-cart, update cart, "
    "checkout) you CALL the Medusa Store API endpoints listed below. Medusa "
    "guarantees correctness; you provide the interactive UI that calls it.\n\n"
    "Do this, in order:\n"
    "1. Read the workspace to understand the starter's structure and the existing "
    "Medusa client in lib/.\n"
    "2. Look at the merchant's products (already seeded in Medusa — fetch them "
    "live). Group them into sensible CATEGORIES/collections and build category "
    "navigation around them.\n"
    "3. Build the storefront: home/landing with the brand's tone, product listing "
    "with working filters, product detail pages, and a working cart + checkout "
    "flow that calls the Medusa endpoints. Use the brand colors/tone. Use the "
    "merchant's store name everywhere (title, header) — never leave it as "
    "'Storefront'.\n"
    "4. Never hardcode or mock product data — always fetch from the Medusa API.\n"
    "5. Verify your work: run `npm run build` and fix any errors until it builds "
    "clean. Keep iterating until the store is complete and the build passes.\n"
    "Edit the starter's components and design tokens; reuse its primitives rather "
    "than reinventing them."
)


def compose_build_prompt(
    *,
    manifest: dict[str, Any],
    base_prompt: str = "",
    brand: dict[str, Any] | None = None,
    business: dict[str, Any] | None = None,
    products: list[dict[str, Any]] | None = None,
    feature_flags: list[str] | None = None,
    user_request: str = "",
    industry: str | None = None,
) -> str:
    """Render the full build prompt. Deterministic given the same inputs."""
    from agent.prompts import load_base_prompt
    from agent.skills import load_skills

    _is_ecommerce = (industry or "").lower() in ("ecommerce", "e-commerce", "restaurant")
    sys_prompt = load_base_prompt() or (_ECOMMERCE_BASE if _is_ecommerce else _DEFAULT_BASE)
    parts: list[str] = [sys_prompt]

    skills = load_skills(industry)
    if skills:
        parts.append(skills)

    if base_prompt.strip():
        parts.append("## Plan\n" + base_prompt.strip())

    if business:
        bits = [f"{k}={v}" for k, v in business.items() if v]
        if bits:
            parts.append("\n## Store\n" + ", ".join(bits))

    backend = manifest.get("backend", "the backend")
    base_url = manifest.get("apiBaseUrlTemplate", "")
    parts.append(f"\n## Backend\n{backend} at {base_url}".rstrip())

    endpoints = manifest.get("endpoints", {})
    if endpoints:
        lines = [
            f"- {name}: {ep.get('method', 'GET')} {ep.get('path', '')}"
            for name, ep in endpoints.items()
        ]
        parts.append("\n## API endpoints\n" + "\n".join(lines))

    shape = manifest.get("product_shape")
    if shape:
        parts.append("\n## Data shape\n" + ", ".join(f"{k}: {v}" for k, v in shape.items()))

    flows = manifest.get("criticalFlows", [])
    if flows:
        parts.append(
            "\n## Critical flows to build AND self-test\n"
            + ", ".join(flows)
        )

    filters = manifest.get("features", {}).get("filters", [])
    if filters:
        parts.append("\n## Filters to wire\n" + ", ".join(filters))

    if products:
        named = [p for p in products if (p.get("name") or "").strip()]
        if named:
            parts.append(
                "\n## Catalog\n"
                f"The merchant's {len(named)} product(s) are ALREADY seeded in the "
                "backend — fetch them from the API, do not hardcode them. Names: "
                + ", ".join(p["name"] for p in named[:20])
            )

    if brand:
        bits = [f"{k}={v}" for k, v in brand.items()]
        parts.append(
            "\n## Brand kit (apply via design tokens only)\n"
            + ", ".join(bits)
            + "\nThe primary/accent colors are ALREADY written into app/globals.css; "
            "build the layout and tone to match this brand."
        )

    if feature_flags:
        parts.append("\n## Requested features\n" + ", ".join(feature_flags))

    if user_request.strip():
        parts.append("\n## Merchant request\n" + user_request.strip())

    return "\n".join(parts).strip() + "\n"
