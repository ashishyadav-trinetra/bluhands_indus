"""BluHands agent client implementations.

Phase 3: StubAgentClient returns immediate success without network I/O.
Real HTTP client wired in T-A01 when the agent service is deployed.
"""

from __future__ import annotations


class StubAgentClient:
    """Fake agent client — immediate success, no network calls.

    Simulates: submit build → poll → success with a stub preview URL.
    """

    async def start_build(
        self,
        build_id: str,
        *,
        prompt: str,
        tenant_id: str,
        industry: str,
        llm_model: str | None = None,
        backend_url: str | None = None,
        publishable_key: str = "",
        manifest: dict | None = None,
    ) -> str:
        return f"stub-job-{build_id}"

    async def get_status(self, job_id: str) -> dict:
        return {
            "status": "success",
            "preview_url": f"https://preview.bluhands.dev/{job_id}",
            "error": None,
        }


class HttpAgentClient:
    """Real client (T-A01): calls the BluHands agent service over HTTP.

    Implements ``BluHandsAgentClientProtocol``:
      start_build -> POST {base}/builds
      get_status  -> GET  {base}/builds/{job_id}
    """

    def __init__(self, base_url: str, *, timeout_seconds: int = 30) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def start_build(
        self,
        build_id: str,
        *,
        prompt: str,
        tenant_id: str,
        industry: str,
        llm_model: str | None = None,
        backend_url: str | None = None,
        publishable_key: str = "",
        manifest: dict | None = None,
    ) -> str:
        import httpx

        body: dict = {
            "build_id": build_id,
            "prompt": prompt,
            "tenant_id": tenant_id,
            "industry": industry,
        }
        if llm_model:
            body["llm_model"] = llm_model
        if backend_url:
            body["backend_url"] = backend_url
        if publishable_key:
            body["publishable_key"] = publishable_key
        if manifest:
            body["manifest"] = manifest
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/builds", json=body)
            resp.raise_for_status()
            return resp.json()["job_id"]

    async def get_status(self, job_id: str) -> dict:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/builds/{job_id}")
            resp.raise_for_status()
            return resp.json()


def get_agent_client(settings):
    """Factory: StubAgentClient (default) or HttpAgentClient based on settings."""
    if getattr(settings, "agent_mode", "stub") == "http":
        return HttpAgentClient(
            settings.agent_base_url, timeout_seconds=settings.agent_timeout_seconds
        )
    return StubAgentClient()
