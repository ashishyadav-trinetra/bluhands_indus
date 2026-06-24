"""Unit tests for the (pure) Medusa seeding payload builders."""

from __future__ import annotations

from agent.medusa_seed import build_product_payload, named_products


def test_build_product_payload_basic() -> None:
    body = build_product_payload(
        {"name": "Classic Tee", "price": "1299", "stock": "50"},
        currency="INR",
        sales_channel_id="sc_1",
    )
    assert body["title"] == "Classic Tee"
    assert body["status"] == "published"
    variant = body["variants"][0]
    assert variant["prices"][0] == {"amount": 1299.0, "currency_code": "inr"}
    assert body["sales_channels"] == [{"id": "sc_1"}]


def test_build_product_payload_parses_messy_price() -> None:
    body = build_product_payload({"name": "X", "price": "₹1,299.50"}, currency="INR")
    assert body["variants"][0]["prices"][0]["amount"] == 1299.50
    # No sales channel given -> key omitted.
    assert "sales_channels" not in body


def test_build_product_payload_defaults_blank_price_to_zero() -> None:
    body = build_product_payload({"name": "Freebie"}, currency="USD")
    assert body["variants"][0]["prices"][0]["amount"] == 0.0
    assert body["variants"][0]["prices"][0]["currency_code"] == "usd"


def test_named_products_skips_blank_rows() -> None:
    rows = [{"name": "A"}, {"name": "  "}, {"name": ""}, {"name": "B"}]
    assert [p["name"] for p in named_products(rows)] == ["A", "B"]
    assert named_products(None) == []
