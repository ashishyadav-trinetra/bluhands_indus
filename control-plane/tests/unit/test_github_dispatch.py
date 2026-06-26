"""Unit tests for the executor's GitHub push/pull context resolution."""

from __future__ import annotations

import types
import uuid

import pytest

from app.tasks.build_executor import BuildTaskExecutor


def _executor(resolver=None) -> BuildTaskExecutor:
    return BuildTaskExecutor(
        builds=None,  # type: ignore[arg-type]
        tenants=None,  # type: ignore[arg-type]
        agent=None,  # type: ignore[arg-type]
        audit=None,  # type: ignore[arg-type]
        github_token_resolver=resolver,
    )


def _run(**kw) -> types.SimpleNamespace:
    base = dict(
        github_repo_url=None,
        github_push=False,
        github_pull=False,
        github_branch=None,
        started_by=None,
    )
    base.update(kw)
    return types.SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_no_context_when_not_opted_in() -> None:
    ex = _executor()
    assert await ex._github_context(_run()) is None
    # repo present but neither push nor pull → still nothing to do
    assert await ex._github_context(_run(github_repo_url="u")) is None


@pytest.mark.asyncio
async def test_context_resolves_token_and_defaults_branch() -> None:
    uid = uuid.uuid4()

    async def resolver(u):
        return "tok" if u == uid else None

    ctx = await _executor(resolver)._github_context(
        _run(github_repo_url="https://github.com/o/r.git", github_push=True, started_by=uid)
    )
    assert ctx is not None
    assert ctx["token"] == "tok"
    assert ctx["push"] is True and ctx["pull"] is False
    assert ctx["branch"] == "main"


@pytest.mark.asyncio
async def test_context_without_resolver_has_no_token() -> None:
    ctx = await _executor()._github_context(
        _run(github_repo_url="u", github_pull=True, started_by=uuid.uuid4())
    )
    assert ctx is not None and ctx["token"] is None and ctx["pull"] is True
