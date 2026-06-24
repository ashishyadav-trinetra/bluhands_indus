"""Unit tests for Sentry init + PII scrubbing."""

from __future__ import annotations

from app.core.config import Settings
from app.core.observability import _scrub, init_sentry


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, jwt_private_key="x", jwt_public_key="x", **kw)


def test_init_sentry_noop_without_dsn() -> None:
    assert init_sentry(_settings(sentry_dsn=None)) is False


def test_scrub_removes_sensitive_request_data() -> None:
    event = {
        "request": {
            "cookies": {"forge_refresh": "secret"},
            "data": {"password": "p"},
            "headers": {"Authorization": "Bearer t", "X-Razorpay-Signature": "sig", "Accept": "*/*"},
        }
    }
    out = _scrub(event, {})
    req = out["request"]
    assert "cookies" not in req
    assert "data" not in req
    assert req["headers"]["Authorization"] == "[scrubbed]"
    assert req["headers"]["X-Razorpay-Signature"] == "[scrubbed]"
    assert req["headers"]["Accept"] == "*/*"
