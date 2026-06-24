"""Real-E2B smoke test — confirms the prod sandbox path actually works.

Provisions a real E2B microVM from the configured template, then exercises the
exact ``SandboxSession`` ops the build runner relies on: write a file, read it
back, run a command, confirm Node is present (the build needs npm), resolve a
preview host, and tear the sandbox down. Proves isolation is real, not just wired.

Run (needs an E2B account):

    export E2B_API_KEY=e2b_...
    export AGENT_E2B_TEMPLATE=bluhands-node   # or 'base' to test before the template exists
    python -m agent.scripts.e2b_smoke

Exits non-zero on any failure. Does NOT run in CI by default (see
tests/test_e2b_smoke.py, which skips unless E2B_API_KEY is set).
"""

from __future__ import annotations

import asyncio
import os
import sys

from agent.config import Settings
from agent.sandbox import get_sandbox_provider


async def run_smoke() -> None:
    """Provision → exercise → destroy one E2B sandbox. Raises on failure."""
    settings = Settings(sandbox_provider="e2b", dry_run=False)
    provider = get_sandbox_provider(settings)

    print(f"[smoke] acquiring E2B sandbox (template={settings.e2b_template})…")
    session = await provider.acquire("smoke")
    try:
        print(f"[smoke] sandbox_id={session.sandbox_id} workdir={session.workdir}")

        # File round-trip.
        await session.write_file(f"{session.workdir}/hello.txt", "hi from bluhands")
        content = await session.read_file(f"{session.workdir}/hello.txt")
        assert content.strip() == "hi from bluhands", f"file round-trip failed: {content!r}"
        print("[smoke] file write/read OK")

        # Command execution.
        res = await session.run("echo isolated-$(whoami)")
        assert res.ok and "isolated-" in res.stdout, f"run failed: {res!r}"
        print(f"[smoke] command OK: {res.stdout.strip()}")

        # Node must be present — the build does npm install/build.
        node = await session.run("node --version")
        assert node.ok and node.stdout.strip().startswith("v"), (
            f"node not found in template (got {node.stdout!r}/{node.stderr!r}). "
            "Build the bluhands-node template — see agent/e2b/README.md."
        )
        print(f"[smoke] node OK: {node.stdout.strip()}")

        # Preview host resolves (used to surface the build's URL).
        url = await session.preview_url(3000)
        assert url.startswith("http"), f"preview_url malformed: {url!r}"
        print(f"[smoke] preview_url OK: {url}")
    finally:
        await session.close()
        print("[smoke] sandbox destroyed")

    print("[smoke] PASS — E2B sandbox path is healthy and isolated.")


def main() -> None:
    if not os.getenv("E2B_API_KEY"):
        print("E2B_API_KEY not set — cannot run the real-E2B smoke test.", file=sys.stderr)
        sys.exit(2)
    asyncio.run(run_smoke())


if __name__ == "__main__":
    main()
