"""Unit tests for StorageFactory and S3StorageProvider.

Uses unittest.mock to avoid a live S3/MinIO dependency.
Tests verify key construction, upload delegation, and presigned URL generation.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.providers.storage import S3StorageProvider, StorageFactory

TENANT_ID = uuid.uuid4()
BUILD_ID = uuid.uuid4()


def _provider(*, default_ttl: int = 900) -> S3StorageProvider:
    return S3StorageProvider(
        bucket="test-bucket",
        region="us-east-1",
        endpoint_url="http://localhost:9000",
        access_key_id="minioadmin",
        secret_access_key="minioadmin",
        default_ttl_seconds=default_ttl,
    )


# ---------------------------------------------------------------------------
# Key construction
# ---------------------------------------------------------------------------


def test_build_key_canonical_format() -> None:
    provider = _provider()
    key = provider.build_key(TENANT_ID, BUILD_ID, "artifacts", "screenshot.png")
    assert key == f"{TENANT_ID}/builds/{BUILD_ID}/artifacts/screenshot.png"


def test_build_key_different_categories() -> None:
    provider = _provider()
    for cat in ("config", "artifacts", "conversation", "deploy"):
        key = provider.build_key(TENANT_ID, BUILD_ID, cat, "file.json")
        assert f"/{cat}/" in key


def test_build_key_includes_tenant_id() -> None:
    """Tenant scoping is mandatory (§4.4 — path must include tenant id)."""
    provider = _provider()
    key = provider.build_key(TENANT_ID, BUILD_ID, "artifacts", "x.png")
    assert str(TENANT_ID) in key


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_calls_put_object_with_correct_args() -> None:
    provider = _provider()
    mock_client = MagicMock()
    mock_client.put_object = MagicMock(return_value={})
    provider._client = mock_client

    key = provider.build_key(TENANT_ID, BUILD_ID, "artifacts", "shot.png")
    returned_key = await provider.upload(key, b"imagedata", content_type="image/png")

    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key=key,
        Body=b"imagedata",
        ContentType="image/png",
    )
    assert returned_key == key


@pytest.mark.asyncio
async def test_upload_returns_key_on_success() -> None:
    provider = _provider()
    provider._client = MagicMock()
    provider._client.put_object = MagicMock(return_value={})
    key = "some/key/file.txt"
    result = await provider.upload(key, b"data")
    assert result == key


# ---------------------------------------------------------------------------
# Presigned URLs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_presigned_url_uses_default_ttl() -> None:
    provider = _provider(default_ttl=300)
    mock_client = MagicMock()
    mock_client.generate_presigned_url = MagicMock(return_value="https://signed.url/x")
    provider._client = mock_client

    url = await provider.presigned_url("some/key")

    mock_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "test-bucket", "Key": "some/key"},
        ExpiresIn=300,
    )
    assert url == "https://signed.url/x"


@pytest.mark.asyncio
async def test_presigned_url_respects_explicit_ttl() -> None:
    provider = _provider(default_ttl=900)
    mock_client = MagicMock()
    mock_client.generate_presigned_url = MagicMock(return_value="https://signed.url/y")
    provider._client = mock_client

    await provider.presigned_url("some/key", ttl_seconds=60)

    _, kwargs = mock_client.generate_presigned_url.call_args
    assert mock_client.generate_presigned_url.call_args[1]["ExpiresIn"] == 60 or \
           mock_client.generate_presigned_url.call_args[0][-1] == 60 or \
           mock_client.generate_presigned_url.call_args.kwargs.get("ExpiresIn") == 60 or \
           mock_client.generate_presigned_url.call_args.args[-1] == 60


@pytest.mark.asyncio
async def test_presigned_url_explicit_ttl_overrides_default() -> None:
    provider = _provider(default_ttl=900)
    mock_client = MagicMock()
    captured = {}

    def _fake_presign(operation, Params, ExpiresIn):
        captured["ttl"] = ExpiresIn
        return "https://x"

    mock_client.generate_presigned_url = _fake_presign
    provider._client = mock_client

    await provider.presigned_url("k", ttl_seconds=120)
    assert captured["ttl"] == 120


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_storage_factory_creates_s3_provider(settings) -> None:
    provider = StorageFactory.create(settings)
    assert isinstance(provider, S3StorageProvider)


def test_storage_factory_uses_settings_bucket(settings) -> None:
    provider = StorageFactory.create(settings)
    assert provider._bucket == settings.s3_bucket
