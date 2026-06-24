"""Unit tests for the sandbox abstraction (local provider + factory)."""

from __future__ import annotations

import sys

import pytest

from agent.config import Settings
from agent.sandbox import E2BSandbox, LocalSandbox, get_sandbox_provider


def test_factory_defaults_to_local() -> None:
    assert isinstance(get_sandbox_provider(Settings()), LocalSandbox)


def test_factory_selects_e2b() -> None:
    s = Settings(sandbox_provider="e2b")
    # No key -> E2BSandbox construction must fail loud (never silently fall back).
    with pytest.raises(RuntimeError):
        get_sandbox_provider(s)


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError):
        get_sandbox_provider(Settings(sandbox_provider="nope"))


@pytest.mark.skipif(sys.platform == "win32", reason="shell semantics differ on win")
async def test_local_session_runs_and_files(tmp_path) -> None:
    provider = LocalSandbox(root=tmp_path)
    sb = await provider.acquire("b1")
    try:
        await sb.write_file("hello.txt", "hi")
        assert await sb.read_file("hello.txt") == "hi"
        res = await sb.run("echo ok")
        assert res.ok and "ok" in res.stdout
        assert (await sb.preview_url(3000)).endswith(":3000")
    finally:
        await sb.close()
