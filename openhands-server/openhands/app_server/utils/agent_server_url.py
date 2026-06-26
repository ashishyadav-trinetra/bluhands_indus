"""Helpers for resolving agent-server URLs used by the app-server backend.

In ``process``/``local`` deployments the agent-server runs on the same host as
the app-server but is exposed to browsers through a reverse proxy (nginx) at a
public URL such as ``https://<host>/runtime/<port>/...`` -- frequently behind a
self-signed certificate. The browser needs that public URL, but the backend
should talk to the agent-server *directly* on localhost to avoid:

* TLS verification failures against the self-signed proxy certificate, and
* an unnecessary network round-trip back out through the proxy.

``to_internal_agent_server_url`` rewrites such a public, proxied URL to a direct
``http://localhost:<port>/...`` URL for backend (server-to-agent) calls. URLs
that are already direct (no ``/runtime/<port>`` segment) are returned unchanged,
and ``remote`` runtimes -- where the agent-server lives on a different host -- are
never rewritten.
"""

import os
import re

# Matches a proxied agent-server URL, e.g.
#   https://192.168.1.26/runtime/18011/api/conversations/<id>
# capturing the runtime port and the remaining path (if any).
_RUNTIME_PROXY_RE = re.compile(r'^https?://[^/]+/runtime/(?P<port>\d+)(?P<rest>/.*)?$')


def to_internal_agent_server_url(url: str) -> str:
    """Rewrite a public, proxied agent-server URL to a direct localhost URL.

    Used for backend (server-to-agent) calls so the app-server reaches the
    co-located agent-server directly instead of going back out through the
    reverse proxy and tripping over its (often self-signed) TLS certificate.

    Only applies to same-host runtimes. ``remote`` runtimes and already-direct
    URLs (no ``/runtime/<port>`` segment) are returned unchanged.

    Args:
        url: The agent-server URL, possibly a proxied
            ``https://<host>/runtime/<port>/...`` URL.

    Returns:
        ``http://localhost:<port>/...`` when the URL is a proxied same-host
        agent-server URL, otherwise the original URL unchanged.
    """
    if not url:
        return url
    if os.getenv('RUNTIME', '').strip().lower() == 'remote':
        return url
    match = _RUNTIME_PROXY_RE.match(url)
    if not match:
        return url
    port = match.group('port')
    rest = match.group('rest') or ''
    return f'http://localhost:{port}{rest}'
