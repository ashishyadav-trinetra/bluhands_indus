"""Sentry error tracking with strict PII scrubbing.

No-op unless ``FORGE_SENTRY_DSN`` is set, so dev/test never phone home.
``send_default_pii=False`` plus a ``before_send`` scrubber ensure tokens,
cookies, signatures, and auth headers never leave the process.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger

_logger = get_logger("observability")

_SENSITIVE_HEADERS = frozenset(
    {"authorization", "cookie", "set-cookie", "x-razorpay-signature", "stripe-signature"}
)


def _scrub(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive request data before an event is sent to Sentry."""
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("cookies", None)
        request.pop("data", None)  # never ship request bodies (may hold secrets)
        headers = request.get("headers")
        if isinstance(headers, dict):
            for name in list(headers):
                if name.lower() in _SENSITIVE_HEADERS:
                    headers[name] = "[scrubbed]"
    return event


def init_sentry(settings: Settings) -> bool:
    """Initialize Sentry if configured. Returns True if enabled.

    Safe to call always: returns False when no DSN is set or the SDK is absent.
    """
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        _logger.warning("sentry_dsn set but sentry-sdk is not installed; skipping")
        return False

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env.value,
        send_default_pii=False,
        traces_sample_rate=0.1,
        before_send=_scrub,
    )
    _logger.info("sentry_initialized", environment=settings.env.value)
    return True
