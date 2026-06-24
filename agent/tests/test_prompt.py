"""Unit tests for compose_build_prompt (pure)."""

from __future__ import annotations

from agent.prompt import compose_build_prompt

_MANIFEST = {
    "backend": "medusa",
    "apiBaseUrlTemplate": "http://localhost:9000",
    "endpoints": {"list_products": {"method": "GET", "path": "/store/products"}},
    "product_shape": {"id": "string", "title": "string"},
    "criticalFlows": ["browse", "add_to_cart", "checkout"],
    "features": {"filters": ["price", "size"]},
}


def test_prompt_includes_backend_endpoints_flows_filters() -> None:
    out = compose_build_prompt(manifest=_MANIFEST, industry="ecommerce")
    assert "medusa at http://localhost:9000" in out
    assert "GET /store/products" in out
    assert "browse, add_to_cart, checkout" in out
    assert "price, size" in out
    assert "npm run build" in out


def test_prompt_includes_brand_flags_and_request() -> None:
    out = compose_build_prompt(
        manifest=_MANIFEST,
        brand={"name": "ThriftCo", "primary": "#1a1a1a"},
        feature_flags=["wishlist"],
        user_request="add a sale banner",
    )
    assert "ThriftCo" in out and "primary=#1a1a1a" in out
    assert "wishlist" in out
    assert "add a sale banner" in out


def test_prompt_includes_business_and_seeded_products() -> None:
    out = compose_build_prompt(
        manifest=_MANIFEST,
        business={"storeName": "Trinetra Threads", "currency": "INR"},
        products=[{"name": "Classic Tee"}, {"name": ""}, {"name": "Hoodie"}],
    )
    assert "Trinetra Threads" in out
    assert "ALREADY seeded" in out
    assert "Classic Tee" in out and "Hoodie" in out
    assert "2 product(s)" in out


def test_prompt_is_deterministic() -> None:
    a = compose_build_prompt(manifest=_MANIFEST)
    b = compose_build_prompt(manifest=_MANIFEST)
    assert a == b
