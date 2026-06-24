"""Opt-in integration test for the real E2B sandbox path.

Skipped unless E2B_API_KEY is set, so the default/offline suite stays green.
When a key is present it provisions a real microVM and runs the full smoke check.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("E2B_API_KEY"),
    reason="E2B_API_KEY not set — skipping real-E2B integration test",
)


async def test_e2b_sandbox_round_trip() -> None:
    from agent.scripts.e2b_smoke import run_smoke

    await run_smoke()  # raises on any failure
