"""Patches httpx User-Agent and qwen model compat for every Python process.

Loaded automatically by CPython's site module during interpreter
initialization (before any user code runs).  Every process that inherits
a PYTHONPATH pointing to this directory gets:
1. A safe User-Agent on every outgoing httpx request (WAF bypass).
2. Patches for qwen3.6-35b-a3b tool schema compatibility.
"""

import httpx as _httpx


def _safe_ua(self, request, **kw):
    request.headers["User-Agent"] = "bluehands-agent/1.0"
    return _orig_send(self, request, **kw)


_orig_send = _httpx.Client.send
_httpx.Client.send = _safe_ua

if hasattr(_httpx, "AsyncClient"):

    async def _safe_ua_async(self, request, **kw):
        request.headers["User-Agent"] = "bluehands-agent/1.0"
        return await _orig_async_send(self, request, **kw)

    _orig_async_send = _httpx.AsyncClient.send
    _httpx.AsyncClient.send = _safe_ua_async

# qwen model compatibility patches (TaskItem.title, security_risk)
try:
    import fix_task_tracker  # noqa: F401
except Exception:
    pass

# Map the frontend's hardcoded /workspace/project onto the process sandbox's
# real workspace, so the Changes tab works instead of raising GitRepositoryError.
try:
    import fix_git_workspace_path  # noqa: F401
except Exception:
    pass

# Short 2-3 word conversation titles instead of the SDK's 50-char sentences.
try:
    import fix_short_titles  # noqa: F401
except Exception:
    pass
