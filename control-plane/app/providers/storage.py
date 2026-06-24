"""Storage provider — S3-compatible object storage (Strategy pattern).

Patterns applied:
- Strategy (§5.2): ``StorageProvider`` protocol; ``S3StorageProvider`` is the
  concrete strategy; ``StorageFactory`` selects the correct one.
- Factory (§5.2): ``StorageFactory.create()`` returns the configured provider.
- DIP (§5.1): callers depend on ``StorageProvider``, not boto3 directly.

Path convention (§4.4): ``{tenant_id}/builds/{build_id}/{category}/``
  where category ∈ {config, artifacts, conversation, deploy}.

Security (§4.4):
  - Private bucket only — no public ACLs.
  - All access via short-TTL presigned URLs (default 15 min from config).
  - UUID-based filenames prevent path traversal.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.core.config import Settings

# ---------------------------------------------------------------------------
# Protocol (abstraction boundary)
# ---------------------------------------------------------------------------


class StorageProvider(Protocol):
    """Minimal S3-compatible storage interface consumed by services."""

    async def upload(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload ``data`` under ``key``; returns the object key."""
        ...

    async def presigned_url(self, key: str, *, ttl_seconds: int) -> str:
        """Return a short-lived presigned GET URL for ``key``."""
        ...

    def build_key(
        self,
        tenant_id: uuid.UUID,
        build_id: uuid.UUID,
        category: str,
        filename: str,
    ) -> str:
        """Construct the canonical S3 object key for a build artifact."""
        ...


# ---------------------------------------------------------------------------
# S3 concrete provider
# ---------------------------------------------------------------------------


class S3StorageProvider:
    """Boto3-backed S3-compatible provider.

    Works with AWS S3 and MinIO (via ``endpoint_url``).  Lazy-imports boto3
    so the module is importable in test environments without the package.

    Args:
        bucket:           Target bucket name.
        region:           AWS region (ignored by MinIO but required by boto3).
        endpoint_url:     Override for MinIO / localstack (``None`` → AWS).
        access_key_id:    AWS/MinIO access key.
        secret_access_key: AWS/MinIO secret key.
        default_ttl_seconds: Default presigned URL lifetime.
    """

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
        default_ttl_seconds: int,
    ) -> None:
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._default_ttl = default_ttl_seconds
        self._client = None  # lazy-initialised in _get_client()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def build_key(
        self,
        tenant_id: uuid.UUID,
        build_id: uuid.UUID,
        category: str,
        filename: str,
    ) -> str:
        """Canonical key: ``{tenant_id}/builds/{build_id}/{category}/{filename}``."""
        return f"{tenant_id}/builds/{build_id}/{category}/{filename}"

    async def upload(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes to S3 under ``key``; returns the key on success."""
        import asyncio

        client = self._get_client()
        await asyncio.to_thread(
            client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    async def presigned_url(self, key: str, *, ttl_seconds: int | None = None) -> str:
        """Generate a presigned GET URL valid for ``ttl_seconds`` seconds."""
        import asyncio

        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        client = self._get_client()
        url: str = await asyncio.to_thread(
            client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl,
        )
        return url

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self):
        """Return (or lazily create) the boto3 S3 client."""
        if self._client is None:
            import boto3

            kwargs: dict = {
                "region_name": self._region,
            }
            if self._endpoint_url:
                kwargs["endpoint_url"] = self._endpoint_url
            if self._access_key_id and self._secret_access_key:
                kwargs["aws_access_key_id"] = self._access_key_id
                kwargs["aws_secret_access_key"] = self._secret_access_key

            self._client = boto3.client("s3", **kwargs)
        return self._client


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class StorageFactory:
    """Creates the correct ``StorageProvider`` from application settings.

    Usage::

        provider = StorageFactory.create(settings)
        key = provider.build_key(tenant_id, build_id, "artifacts", "screenshot.png")
        await provider.upload(key, data, content_type="image/png")
        url  = await provider.presigned_url(key, ttl_seconds=300)
    """

    @staticmethod
    def create(settings: Settings) -> S3StorageProvider:
        """Instantiate the S3 provider from ``settings``."""
        return S3StorageProvider(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            default_ttl_seconds=settings.s3_signed_url_ttl_seconds,
        )
