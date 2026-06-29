# IMPORTANT: LEGACY V0 CODE - Deprecated since version 1.0.0, scheduled for removal April 1, 2026
# This file is part of the legacy (V0) implementation of OpenHands and will be removed soon as we complete the migration to V1.
# OpenHands V1 uses the Software Agent SDK for the agentic core and runs a new application server. Please refer to:
#   - V1 agentic core (SDK): https://github.com/OpenHands/software-agent-sdk
#   - V1 application server (in this repo): openhands/app_server/
# Unless you are working on deprecation, please avoid extending this legacy file and consult the V1 codepaths above.
# Tag: Legacy-V0
# This module belongs to the old V0 web server. The V1 application server lives under openhands/app_server/.

import os

# Patch httpx to handle non-ASCII header values (em dashes in skill content etc.)
import httpx._models as _oh_httpx_models  # noqa: E402

# The Cloudflare WAF on api.bluehands.ai blocks the OpenAI Python SDK's default
# User-Agent ("OpenAI/Python ...").  We override it at the httpx transport
# layer so every outgoing request from this process uses a safe UA,
# regardless of which library (OpenAI SDK, LiteLLM, etc.) creates it.
import httpx as _oh_httpx  # noqa: E402

_oh_orig_send = _oh_httpx.Client.send


def _oh_safe_ua_send(self: _oh_httpx.Client, request: _oh_httpx.Request, **kw: object) -> _oh_httpx.Response:
    request.headers["User-Agent"] = "bluehands-agent/1.0"
    return _oh_orig_send(self, request, **kw)


_oh_httpx.Client.send = _oh_safe_ua_send

if hasattr(_oh_httpx, "AsyncClient"):
    _oh_orig_async_send = _oh_httpx.AsyncClient.send

    async def _oh_safe_ua_async_send(self: _oh_httpx.AsyncClient, request: _oh_httpx.Request, **kw: object) -> _oh_httpx.Response:  # type: ignore[type-arg]
        request.headers["User-Agent"] = "bluehands-agent/1.0"
        return await _oh_orig_async_send(self, request, **kw)  # type: ignore[misc]

    _oh_httpx.AsyncClient.send = _oh_safe_ua_async_send  # type: ignore[assignment]

from openhands.server.app import app as base_app
from openhands.server.middleware import (
    CacheControlMiddleware,
    InMemoryRateLimiter,
    LocalhostCORSMiddleware,
    RateLimitMiddleware,
)
from openhands.server.static import SPAStaticFiles

_oh_orig = _oh_httpx_models._normalize_header_value


def _oh_patched(value, encoding=None):
    if isinstance(value, bytes):
        return value
    try:
        return value.encode(encoding or 'ascii')
    except UnicodeEncodeError:
        return value.encode(encoding or 'ascii', errors='replace')


_oh_httpx_models._normalize_header_value = _oh_patched
_oh_httpx_models._normalize_header_key = _oh_patched

if os.getenv('SERVE_FRONTEND', 'true').lower() == 'true':
    base_app.mount(
        '/', SPAStaticFiles(directory='./frontend/build', html=True), name='dist'
    )

base_app.add_middleware(LocalhostCORSMiddleware)
base_app.add_middleware(CacheControlMiddleware)
base_app.add_middleware(
    RateLimitMiddleware,
    rate_limiter=InMemoryRateLimiter(requests=10, seconds=1),
)

# Note: socketio is no longer used for communication. The base FastAPI app is used directly.
app = base_app
