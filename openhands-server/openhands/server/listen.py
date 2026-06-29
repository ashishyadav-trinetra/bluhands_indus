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
# User-Agent ("OpenAI/Python ...").  We use TWO patches to ensure a safe UA:
# 1. Override the `user_agent` property on BaseClient (affects _default_headers).
# 2. Wrap `_build_headers` to force the User-Agent after all merging.
# Together they cover all SDK v1/v2 patterns and any custom-header overrides.
import openai._base_client as _oai_base  # noqa: E402

_oai_base.BaseClient.user_agent = property(lambda self: "bluehands-agent/1.0")

_orig_build_headers = _oai_base.BaseClient._build_headers


def _patched_build_headers(self, *args: object, **kw: object) -> object:
    headers = _orig_build_headers(self, *args, **kw)
    headers["User-Agent"] = "bluehands-agent/1.0"
    return headers


_oai_base.BaseClient._build_headers = _patched_build_headers

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
