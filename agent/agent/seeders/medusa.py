"""Medusa ecommerce seeder — registered for industry="ecommerce".

Thin wrapper that adapts the generic runner kwargs to the existing
``medusa_seed.seed_products`` call. All the pure logic lives in
``agent.medusa_seed`` so its unit tests are unaffected.
"""

from __future__ import annotations

from typing import Any


async def seed(
    *,
    backend_url: str | None,
    admin_email: str,
    admin_password: str,
    products: list[dict[str, Any]] | None,
    business: dict[str, Any] | None = None,
    **_kwargs: Any,  # absorb any future runner kwargs
) -> None:
    """Push the merchant's onboarding products into their Medusa instance."""
    if not (products and backend_url and admin_email and admin_password):
        return
    from agent.medusa_seed import seed_products

    currency = (business or {}).get("currency", "usd")
    await seed_products(
        medusa_url=backend_url,
        admin_email=admin_email,
        admin_password=admin_password,
        products=products,
        currency=currency,
    )
