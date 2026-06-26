"""GitHub via Nango.

The user connects GitHub through Nango's ConnectUI (the existing
``/integrations/session`` + ``/connections`` flow). This service uses that Nango
connection to: report status, fetch the GitHub access token (so the agent can
push/pull inside the sandbox), and list/create repos.

We resolve the user's GitHub connection by the ``end_user_id`` tag Nango stores
(set when the session is created), then read its credentials. Nango response
shapes vary slightly by version, so parsing is defensive.
"""

from __future__ import annotations

import uuid

import httpx

from app.core.config import Settings
from app.core.exceptions import AppError, NotFoundError

_GITHUB_API = "https://api.github.com"


def _gh_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


class GithubService:
    """GitHub operations backed by a Nango connection."""

    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    @property
    def _provider_key(self) -> str:
        return self._settings.nango_github_provider_key

    def _nango_headers(self) -> dict[str, str]:
        if not self._settings.nango_secret_key:
            raise AppError(
                "Nango is not configured — set FORGE_NANGO_SECRET_KEY",
                code="NANGO_NOT_CONFIGURED",
                http_status=503,
            )
        return {"Authorization": f"Bearer {self._settings.nango_secret_key}"}

    async def _connection_id(self, user_id: uuid.UUID) -> str | None:
        """Find the user's GitHub connection id from Nango (by end_user_id tag)."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._settings.nango_base_url}/connections",
                headers=self._nango_headers(),
                params={"tags[end_user_id]": str(user_id)},
            )
            resp.raise_for_status()
            data = resp.json()
        conns = data.get("connections") or data.get("data") or []
        for conn in conns:
            key = conn.get("provider_config_key") or conn.get("provider")
            if key == self._provider_key:
                return conn.get("connection_id") or conn.get("connectionId") or conn.get("id")
        return None

    async def get_status(self, user_id: uuid.UUID) -> dict:
        """Whether the user has a GitHub connection in Nango."""
        return {"connected": await self._connection_id(user_id) is not None}

    async def get_token(self, user_id: uuid.UUID) -> str | None:
        """Return the user's GitHub access token from Nango, or None if unconnected."""
        connection_id = await self._connection_id(user_id)
        if not connection_id:
            return None
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._settings.nango_base_url}/connection/{connection_id}",
                headers=self._nango_headers(),
                params={"provider_config_key": self._provider_key},
            )
            resp.raise_for_status()
            data = resp.json()
        creds = data.get("credentials") or {}
        return creds.get("access_token") or (creds.get("raw") or {}).get("access_token")

    async def _require_token(self, user_id: uuid.UUID) -> str:
        token = await self.get_token(user_id)
        if not token:
            raise NotFoundError("GitHub is not connected")
        return token

    async def list_repos(self, user_id: uuid.UUID) -> list[dict]:
        token = await self._require_token(user_id)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{_GITHUB_API}/user/repos?per_page=100&sort=updated&affiliation=owner",
                headers=_gh_headers(token),
            )
            resp.raise_for_status()
            return [
                {
                    "name": r["name"],
                    "full_name": r["full_name"],
                    "private": r["private"],
                    "clone_url": r["clone_url"],
                }
                for r in resp.json()
            ]

    async def create_repo(self, user_id: uuid.UUID, name: str, *, private: bool = True) -> dict:
        token = await self._require_token(user_id)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{_GITHUB_API}/user/repos",
                headers=_gh_headers(token),
                json={"name": name, "private": private, "auto_init": False},
            )
            resp.raise_for_status()
            r = resp.json()
            return {"name": r["name"], "full_name": r["full_name"], "clone_url": r["clone_url"]}
