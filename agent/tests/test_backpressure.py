"""Unit tests for build backpressure (concurrency cap) + the prod isolation guard."""

from __future__ import annotations

import asyncio

import pytest

from agent.config import Settings
from agent.jobs import CapacityError, JobStore
from agent.runner import BuildOutcome, BuildSpec
from agent.sandbox import LocalSandbox, get_sandbox_provider


class _BlockingRunner:
    """Runner that hangs until released, so builds stay 'active'."""

    def __init__(self) -> None:
        self.gate = asyncio.Event()

    async def run(self, spec: BuildSpec) -> BuildOutcome:
        await self.gate.wait()
        return BuildOutcome(success=True, preview_url="x")


def _spec(i: int) -> BuildSpec:
    return BuildSpec(build_id=f"b{i}", prompt="", tenant_id="t", industry="")


async def test_capacity_rejects_when_full_then_frees() -> None:
    runner = _BlockingRunner()
    store = JobStore(runner, max_concurrent=2)

    await store.start(_spec(1))
    await store.start(_spec(2))
    assert store.active == 2

    with pytest.raises(CapacityError):
        await store.start(_spec(3))

    # Release the in-flight builds; capacity should free up.
    runner.gate.set()
    for _ in range(20):
        await asyncio.sleep(0)
        if store.active == 0:
            break
    assert store.active == 0
    await store.start(_spec(4))  # succeeds again
    runner.gate.set()


def test_prod_refuses_local_sandbox() -> None:
    with pytest.raises(RuntimeError):
        get_sandbox_provider(Settings(sandbox_provider="local", env="production"))


def test_dev_allows_local_sandbox() -> None:
    provider = get_sandbox_provider(Settings(sandbox_provider="local", env="development"))
    assert isinstance(provider, LocalSandbox)
