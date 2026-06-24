"""ApiKeyService — create / list / revoke / authenticate admin API keys.

Security (CODING-STANDARDS §4.5/§6.3): only the SHA-256 hash is stored; the
plaintext is returned once at creation. Authentication looks up by hash,
rejects revoked keys, records last_used_at, and logs usage to the audit trail.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.security import generate_api_key, hash_api_key
from app.db.models.api_key import ApiKey
from app.services.protocols import ApiKeyRepositoryProtocol, AuditLoggerProtocol


class ApiKeyService:
    """Manages the lifecycle and authentication of API keys."""

    def __init__(self, *, keys: ApiKeyRepositoryProtocol, audit: AuditLoggerProtocol) -> None:
        self._keys = keys
        self._audit = audit

    async def create_key(
        self,
        org_id: uuid.UUID,
        *,
        name: str,
        rate_limit_per_min: int = 100,
        actor: str,
        ip: str | None = None,
    ) -> tuple[ApiKey, str]:
        """Create a key. Returns ``(key_row, plaintext)`` — plaintext shown once."""
        plaintext, prefix, key_hash = generate_api_key(live=True)
        key = ApiKey(
            org_id=org_id,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            rate_limit_per_min=rate_limit_per_min,
        )
        await self._keys.add(key)
        await self._audit.record(
            AuditEvent(actor=actor, org_id=org_id, action="apikey.created", target=prefix, ip=ip)
        )
        return key, plaintext

    async def list_keys(self, org_id: uuid.UUID) -> list[ApiKey]:
        """List an organization's API keys (no secrets)."""
        return await self._keys.list_for_org(org_id)

    async def revoke_key(
        self, org_id: uuid.UUID, key_id: uuid.UUID, *, actor: str, ip: str | None = None
    ) -> None:
        """Revoke a key (idempotent). Raises NotFoundError if it isn't this org's."""
        key = await self._keys.get_by_id(key_id)
        if key is None or key.org_id != org_id:
            raise NotFoundError("API key not found.")
        if key.revoked_at is None:
            key.revoked_at = datetime.now(timezone.utc)
        await self._audit.record(
            AuditEvent(actor=actor, org_id=org_id, action="apikey.revoked", target=key.prefix, ip=ip)
        )

    async def authenticate(self, plaintext: str) -> ApiKey:
        """Authenticate a presented key. Records usage; rejects unknown/revoked.

        Raises:
            AuthenticationError: if the key is unknown or revoked.
        """
        key = await self._keys.get_by_hash(hash_api_key(plaintext))
        if key is None or key.revoked_at is not None:
            raise AuthenticationError("Invalid API key")
        key.last_used_at = datetime.now(timezone.utc)
        await self._audit.record(
            AuditEvent(actor=f"apikey:{key.id}", org_id=key.org_id, action="apikey.used", target=key.prefix)
        )
        return key
