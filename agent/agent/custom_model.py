"""Custom (self-hosted) OpenAI-compatible model client.

The Cloudflare WAF on api.bluehands.ai blocks the ``User-Agent: OpenAI/Python ...``
header that the openai Python SDK sends by default.  This module provides a clean
httpx transport that strips the ``x-stainless-*`` headers and overrides the UA.

Usage from ``llm.py``:

    from agent.custom_model import bluehands_client

    client = bluehands_client(base_url="https://api.bluehands.ai/v1")
    resp = client.chat.completions.create(model="qwen3.6-35b-a3b", ...)
"""

from __future__ import annotations

from typing import Any

import httpx
from openai import OpenAI


class _CleanClient(httpx.Client):
    """httpx.Client that strips headers the WAF blocks and overrides UA."""

    def send(self, request: httpx.Request, *args: Any, **kwargs: Any) -> httpx.Response:
        for key in list(request.headers.keys()):
            if key.lower().startswith("x-stainless-"):
                del request.headers[key]
        request.headers["user-agent"] = "bluehands-agent/1.0"
        return super().send(request, *args, **kwargs)


def bluehands_client(
    base_url: str = "https://api.bluehands.ai/v1",
    api_key: str = "anything",
) -> OpenAI:
    """Return an OpenAI-compatible client for a custom vLLM endpoint.

    The returned client strips ``x-stainless-*`` headers and uses a safe
    ``User-Agent`` — required for the Cloudflare WAF on ``api.bluehands.ai``.
    """
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=_CleanClient(),
    )
