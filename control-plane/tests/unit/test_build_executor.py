"""Unit tests for BuildTaskExecutor FSM.

All tests are fully offline — no DB, no Celery, no agent network calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.db.models.build_run import BuildRun
from app.db.models.enums import BuildStatus
from app.tasks.build_executor import BuildTaskExecutor, FSMError
from tests.fakes import FakeAgentClient, InMemoryAudit, InMemoryBuildRunRepo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _queued_build(tenant_id: uuid.UUID | None = None) -> BuildRun:
    b = BuildRun(
        tenant_id=tenant_id or uuid.uuid4(),
        status=BuildStatus.QUEUED,
        prompt="Build a restaurant booking app.",
        credits_cost=100,
    )
    b.id = uuid.uuid4()
    b.created_at = datetime.now(timezone.utc)
    b.updated_at = datetime.now(timezone.utc)
    return b


def _executor(
    build: BuildRun,
    *,
    agent: FakeAgentClient | None = None,
) -> tuple[BuildTaskExecutor, InMemoryBuildRunRepo, FakeAgentClient, InMemoryAudit]:
    from tests.fakes import InMemoryTenantRepo

    repo = InMemoryBuildRunRepo()
    repo._by_id[build.id] = build
    fake_agent = agent or FakeAgentClient()
    audit = InMemoryAudit()
    exc = BuildTaskExecutor(
        builds=repo,
        tenants=InMemoryTenantRepo(),
        agent=fake_agent,
        audit=audit,
    )
    return exc, repo, fake_agent, audit


# ---------------------------------------------------------------------------
# Happy-path FSM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_happy_path_reaches_review() -> None:
    build = _queued_build()
    executor, repo, _, audit = _executor(build)

    await executor.execute(str(build.id))

    stored = await repo.get_by_id(build.id)
    assert stored.status == BuildStatus.REVIEW


@pytest.mark.asyncio
async def test_execute_sets_preview_url() -> None:
    build = _queued_build()
    executor, repo, agent, _ = _executor(build)

    await executor.execute(str(build.id))

    stored = await repo.get_by_id(build.id)
    assert stored.preview_url is not None
    assert "preview.bluhands.dev" in stored.preview_url


@pytest.mark.asyncio
async def test_execute_stores_conversation_id() -> None:
    build = _queued_build()
    executor, repo, _, _ = _executor(build)

    await executor.execute(str(build.id))

    stored = await repo.get_by_id(build.id)
    assert stored.conversation_id is not None
    assert str(build.id) in stored.conversation_id


@pytest.mark.asyncio
async def test_execute_emits_review_ready_audit_event() -> None:
    build = _queued_build()
    executor, _, _, audit = _executor(build)

    await executor.execute(str(build.id))

    assert "build.review_ready" in audit.actions()


@pytest.mark.asyncio
async def test_execute_calls_agent_start_build() -> None:
    build = _queued_build()
    executor, _, agent, _ = _executor(build)

    await executor.execute(str(build.id))

    assert len(agent.started) == 1
    assert agent.started[0]["build_id"] == str(build.id)
    assert agent.started[0]["prompt"] == build.prompt


@pytest.mark.asyncio
async def test_execute_polls_agent_status() -> None:
    build = _queued_build()
    executor, _, agent, _ = _executor(build)

    await executor.execute(str(build.id))

    assert len(agent.polled) == 1


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_unknown_build_id_raises_value_error() -> None:
    build = _queued_build()
    executor, _, _, _ = _executor(build)

    with pytest.raises(ValueError, match="not found"):
        await executor.execute(str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_execute_non_queued_build_raises_value_error() -> None:
    build = _queued_build()
    build.status = BuildStatus.BUILDING  # already in progress
    executor, _, _, _ = _executor(build)

    with pytest.raises(ValueError, match="QUEUED"):
        await executor.execute(str(build.id))


@pytest.mark.asyncio
async def test_execute_agent_start_failure_transitions_to_failed() -> None:
    build = _queued_build()
    agent = FakeAgentClient(fail=True)
    executor, repo, _, audit = _executor(build, agent=agent)

    with pytest.raises(RuntimeError, match="Agent service unavailable"):
        await executor.execute(str(build.id))

    stored = await repo.get_by_id(build.id)
    assert stored.status == BuildStatus.FAILED
    assert "build.failed" in audit.actions()


@pytest.mark.asyncio
async def test_execute_agent_poll_failure_transitions_to_failed() -> None:
    build = _queued_build()
    agent = FakeAgentClient(fail_on_poll=True)
    executor, repo, _, audit = _executor(build, agent=agent)

    with pytest.raises(RuntimeError, match="Agent reported failure"):
        await executor.execute(str(build.id))

    stored = await repo.get_by_id(build.id)
    assert stored.status == BuildStatus.FAILED


@pytest.mark.asyncio
async def test_execute_failed_build_records_error_message() -> None:
    build = _queued_build()
    agent = FakeAgentClient(fail=True)
    executor, repo, _, _ = _executor(build, agent=agent)

    with pytest.raises(RuntimeError):
        await executor.execute(str(build.id))

    stored = await repo.get_by_id(build.id)
    assert stored.error is not None
    assert "unavailable" in stored.error


# ---------------------------------------------------------------------------
# FSM transition guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fsm_guard_rejects_invalid_transition() -> None:
    """_transition must reject QUEUED → BUILDING (skipping PROVISIONING)."""
    build = _queued_build()
    executor, _, _, _ = _executor(build)

    with pytest.raises(FSMError):
        await executor._transition(build, to=BuildStatus.BUILDING)
