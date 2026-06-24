"""Unit tests for runners + runner selection (offline, DryRun)."""

from __future__ import annotations

import pytest

from agent.config import Settings
from agent.runner import DryRunRunner, OpenHandsRunner, BuildSpec, get_runner


def _settings(tmp_path, **kw) -> Settings:
    return Settings(_env_file=None, workspace_root=tmp_path, **kw)


@pytest.mark.asyncio
async def test_dryrun_runner_succeeds_and_writes_marker(tmp_path) -> None:
    s = _settings(tmp_path, preview_base_url="https://preview.test")
    outcome = await DryRunRunner(s).run(
        BuildSpec(build_id="b1", prompt="make a shop", tenant_id="t1", industry="ecommerce")
    )
    assert outcome.success is True
    assert outcome.preview_url == "https://preview.test/b1"
    assert (tmp_path / "b1" / "BUILD.txt").exists()


def test_get_runner_defaults_to_dryrun(tmp_path) -> None:
    # dry_run defaults True → DryRunRunner even if a key were present.
    assert isinstance(get_runner(_settings(tmp_path)), DryRunRunner)


def test_get_runner_real_requires_key(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # dry_run off but no key → still DryRun (safe default).
    assert isinstance(get_runner(_settings(tmp_path, dry_run=False)), DryRunRunner)
    # dry_run off AND key present → real runner.
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert isinstance(get_runner(_settings(tmp_path, dry_run=False)), OpenHandsRunner)
