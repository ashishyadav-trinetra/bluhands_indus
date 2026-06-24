"""DomainService — availability checks and Entri DNS-connect session management.

Entri (https://entri.com) provides:
- A REST API for domain availability and purchase
- A JavaScript widget that auto-configures DNS at the user's registrar

When ``entri_api_key`` is not set the service returns deterministic stubs so
the full onboarding flow works in dev without entri credentials.

Entri API base: https://api.entri.com
  GET  /domains/availability?domain=xxx   — availability check
  POST /v1/sessions                       — create DNS-connect session token
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_STUB_PRICE = 99900   # 999 INR in paise
_STUB_TOKEN = "stub-entri-session"


class DomainService:
    """Thin wrapper around the Entri API with offline fallback."""

    def __init__(
        self,
        *,
        entri_api_key: str | None,
        entri_app_id: str,
        entri_api_url: str,
        platform_a_record: str,
        platform_cname: str,
    ) -> None:
        self._api_key = entri_api_key
        self._app_id = entri_app_id
        self._api_url = entri_api_url.rstrip("/")
        self._a_record = platform_a_record
        self._cname = platform_cname

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def check_availability(self, domain: str) -> dict:
        """Return availability info for *domain*.

        Returns dict with keys: domain, available, price_minor, currency.
        """
        if not self._api_key:
            return self._stub_availability(domain)

        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._api_url}/domains/availability",
                    params={"domain": domain},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "domain": domain,
                    "available": data.get("available", False),
                    "price_minor": data.get("price", {}).get("amount", _STUB_PRICE),
                    "currency": data.get("price", {}).get("currency", "INR").upper(),
                }
        except Exception:
            logger.exception("entri availability check failed for %s", domain)
            return self._stub_availability(domain)

    async def create_session(self, domain: str) -> str:
        """Generate an Entri session token for the DNS-connect widget.

        Returns the session token string. Falls back to a stub token when no
        API key is configured.
        """
        if not self._api_key:
            return _STUB_TOKEN

        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self._api_url}/v1/sessions",
                    json={"domain": domain, "applicationId": self._app_id},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                resp.raise_for_status()
                return resp.json()["token"]
        except Exception:
            logger.exception("entri session creation failed for %s", domain)
            return _STUB_TOKEN

    def platform_dns_records(self, domain: str) -> list[dict]:
        """Return the DNS records the platform needs for a given domain."""
        return [
            {"type": "A", "host": "@", "value": self._a_record, "ttl": 300},
            {"type": "CNAME", "host": "www", "value": self._cname, "ttl": 300},
            {"type": "TXT", "host": "_bluhands", "value": f"verify={domain}", "ttl": 300},
        ]

    @property
    def app_id(self) -> str:
        return self._app_id

    # ------------------------------------------------------------------
    # Stubs
    # ------------------------------------------------------------------

    def _stub_availability(self, domain: str) -> dict:
        available = "taken" not in domain.lower() and "." in domain
        return {
            "domain": domain,
            "available": available,
            "price_minor": _STUB_PRICE,
            "currency": "INR",
        }
