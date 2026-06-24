"""Seed the merchant's onboarding products into their Medusa store.

Runs before the agent builds, so the live storefront shows the merchant's real
catalog instead of the demo seed. Uses the Medusa v2 Admin API:

    POST /auth/user/emailpass        -> bearer token
    GET  /admin/sales-channels       -> default sales channel
    POST /admin/products             -> create product (published, priced)

``build_product_payload`` is pure and unit-tested; ``seed_products`` is the thin
network wrapper. Best-effort: a single product failing is logged and skipped so
one bad row never sinks the whole build.

NOTE: Medusa v2 expects ``prices[].amount`` as a decimal in the major currency
unit (e.g. 19.99). If your Medusa build uses minor units, flip ``_to_amount``.
"""

from __future__ import annotations

from typing import Any


def _to_amount(price: str) -> float:
    """Parse a raw price string (e.g. '19.99', '₹1,299') to a decimal amount."""
    cleaned = "".join(c for c in str(price) if c.isdigit() or c == ".")
    try:
        return round(float(cleaned), 2) if cleaned else 0.0
    except ValueError:
        return 0.0


def _to_stock(stock: str) -> int:
    digits = "".join(c for c in str(stock) if c.isdigit())
    return int(digits) if digits else 0


def build_product_payload(
    product: dict[str, Any],
    *,
    currency: str,
    sales_channel_id: str | None = None,
) -> dict[str, Any]:
    """Build the POST /admin/products body for one onboarding product (pure).

    A single default variant carries the price; no size/color options (the
    merchant can add variants later in their dashboard).
    """
    name = (product.get("name") or "Untitled product").strip()
    amount = _to_amount(product.get("price", ""))
    currency_code = currency.lower()

    payload: dict[str, Any] = {
        "title": name,
        "status": "published",
        "description": product.get("description", ""),
        "options": [{"title": "Default", "values": ["Default"]}],
        "variants": [
            {
                "title": name,
                "manage_inventory": False,
                "prices": [{"amount": amount, "currency_code": currency_code}],
                "options": {"Default": "Default"},
            }
        ],
    }
    if sales_channel_id:
        payload["sales_channels"] = [{"id": sales_channel_id}]
    return payload


def named_products(products: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Filter to products the merchant actually named (skip blank rows)."""
    return [p for p in (products or []) if (p.get("name") or "").strip()]


async def seed_products(
    *,
    medusa_url: str,
    admin_email: str,
    admin_password: str,
    products: list[dict[str, Any]],
    currency: str,
    timeout_seconds: int = 30,
) -> list[str]:
    """Create the given products in Medusa. Returns the created product ids.

    Raises:
        RuntimeError: if admin authentication fails (nothing can be seeded).
    """
    import httpx

    rows = named_products(products)
    if not rows:
        return []

    base = medusa_url.rstrip("/")
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        auth = await client.post(
            f"{base}/auth/user/emailpass",
            json={"email": admin_email, "password": admin_password},
        )
        if auth.status_code != 200:
            raise RuntimeError(
                f"Medusa admin auth failed ({auth.status_code}): {auth.text[:200]}"
            )
        token = auth.json().get("token")
        if not token:
            raise RuntimeError("Medusa admin auth returned no token.")
        headers = {"Authorization": f"Bearer {token}"}

        # Default sales channel so the products are visible to the storefront.
        sc_id: str | None = None
        sc = await client.get(f"{base}/admin/sales-channels", headers=headers)
        if sc.status_code == 200:
            channels = sc.json().get("sales_channels", [])
            if channels:
                sc_id = channels[0]["id"]

        created: list[str] = []
        for row in rows:
            body = build_product_payload(row, currency=currency, sales_channel_id=sc_id)
            resp = await client.post(f"{base}/admin/products", json=body, headers=headers)
            if resp.status_code in (200, 201):
                created.append(resp.json().get("product", {}).get("id", ""))
            # else: skip — best-effort; the build continues with what seeded.
        return [c for c in created if c]
