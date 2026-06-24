"""Unit tests for prepare_workspace (offline file ops)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.pipeline import prepare_workspace


def _fake_starter(tmp_path: Path) -> Path:
    starter = tmp_path / "starter"
    (starter / "app").mkdir(parents=True)
    (starter / "app" / "page.tsx").write_text("export default function P(){}", encoding="utf-8")
    (starter / "package.json").write_text("{}", encoding="utf-8")
    # should be ignored on copy:
    (starter / "node_modules").mkdir()
    (starter / "node_modules" / "junk.txt").write_text("x", encoding="utf-8")
    return starter


def test_prepare_copies_starter_and_writes_env(tmp_path: Path) -> None:
    starter = _fake_starter(tmp_path)
    ws = tmp_path / "ws"
    prepare_workspace(
        workspace=ws,
        starter_dir=starter,
        medusa_url="http://localhost:9000",
        publishable_key="pk_test",
    )
    assert (ws / "app" / "page.tsx").exists()
    assert (ws / "package.json").exists()
    assert not (ws / "node_modules").exists()  # ignored
    env = (ws / ".env.local").read_text()
    assert "NEXT_PUBLIC_MEDUSA_URL=http://localhost:9000" in env
    assert "NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY=pk_test" in env


def test_prepare_missing_starter_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        prepare_workspace(
            workspace=tmp_path / "ws",
            starter_dir=tmp_path / "does-not-exist",
            medusa_url="http://localhost:9000",
        )
