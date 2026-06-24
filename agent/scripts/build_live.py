"""Drive one REAL end-to-end build, in-process (no HTTP service needed).

It runs the full live pipeline: seed products into Medusa -> prepare the starter
-> apply brand -> OpenHands customizes -> npm build -> serve a preview on a port
-> Playwright self-test. Prints the preview URL at the end.

Prereqs:
  - Medusa running (default http://localhost:9000) with an admin user.
  - OPENROUTER_API_KEY set in the environment.
  - Node/npm available on PATH; `pip install -e .[agent]` (openhands + playwright).

Usage (PowerShell):
  $env:OPENROUTER_API_KEY="sk-or-..."
  python scripts/build_live.py `
    --publishable-key pk_... `
    --admin-email you@example.com --admin-password "yourpass" `
    --input sample        # or a path to an onboarding JSON export

The onboarding JSON (when not "sample") is the wizard's data object:
  { "business": {...}, "brand": {...}, "catalog": {"products": [...]}, "domain": {...} }
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

# Make `agent` importable when run from the repo root or this folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.config import Settings  # noqa: E402
from agent.runner import BuildSpec, OpenHandsRunner  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "catalog" / "ecommerce" / "medusa" / "capability-manifest.json"
STARTER = REPO / "apps" / "starters" / "ecommerce-next"

SAMPLE = {
    "business": {"storeName": "Trinetra Threads", "category": "Apparel", "country": "IN", "currency": "INR"},
    "brand": {"tagline": "Wear the difference.", "primaryColor": "#2d3e63", "accentColor": "#e2725b", "vibe": "premium"},
    "catalog": {
        "products": [
            {"name": "Classic Tee", "price": "1299", "stock": "50", "images": []},
            {"name": "Heavy Hoodie", "price": "2999", "stock": "30", "images": []},
        ]
    },
    "domain": {"mode": "subdomain", "domain": "trinetra-threads.bluhands.app"},
}


def load_input(value: str) -> dict:
    if value == "sample":
        return SAMPLE
    data = json.loads(Path(value).read_text(encoding="utf-8"))
    return data.get("data", data)  # accept either the raw data or {data: ...}


async def main() -> int:
    ap = argparse.ArgumentParser(description="Run one real BluHands build.")
    ap.add_argument("--input", default="sample", help='"sample" or path to onboarding JSON')
    ap.add_argument("--medusa-url", default="http://localhost:9000")
    # Not required at parse time: resume mode (--skip-agent) doesn't need them.
    # Validated below for a normal (agent) run.
    ap.add_argument("--publishable-key", default="")
    ap.add_argument("--admin-email", default="")
    ap.add_argument("--admin-password", default="")
    ap.add_argument("--preview-port", type=int, default=4321)
    ap.add_argument("--workspace-root", default="")
    ap.add_argument(
        "--build-id",
        default="",
        help="Reuse a fixed workspace id (e.g. an existing build) instead of a random one.",
    )
    ap.add_argument(
        "--skip-agent",
        action="store_true",
        help="Resume: reuse the existing built workspace and just build+serve (no LLM cost). "
        "Requires --build-id pointing at a prior build.",
    )
    args = ap.parse_args()

    if args.skip_agent and not args.build_id:
        ap.error("--skip-agent requires --build-id (the workspace to reuse)")
    if not args.skip_agent and not (args.publishable_key and args.admin_email and args.admin_password):
        ap.error("a normal run needs --publishable-key, --admin-email and --admin-password")

    data = load_input(args.input)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    settings = Settings(dry_run=False)  # type: ignore[call-arg]
    if args.workspace_root:
        settings = Settings(dry_run=False, workspace_root=Path(args.workspace_root))  # type: ignore[call-arg]

    if not settings.openrouter_api_key():
        print("WARNING: OPENROUTER_API_KEY not set — the AI customization step will be "
              "skipped (you'll still get a branded, working store from the starter).")

    spec = BuildSpec(
        build_id=args.build_id or f"live-{uuid.uuid4().hex[:8]}",
        prompt="",
        tenant_id="local-dev",
        industry="ecommerce",
        manifest=manifest,
        brand=data.get("brand"),
        business=data.get("business"),
        products=(data.get("catalog") or {}).get("products"),
        medusa_url=args.medusa_url,
        publishable_key=args.publishable_key,
        admin_email=args.admin_email,
        admin_password=args.admin_password,
        starter_dir=str(STARTER),
        preview_port=args.preview_port,
        skip_agent=args.skip_agent,
    )

    print(f"Starting build {spec.build_id} …")
    runner = OpenHandsRunner(settings)
    outcome = await runner.run(spec)

    if outcome.success:
        print(f"\n✅ Build succeeded. Preview: {outcome.preview_url}")
        print("Leave this process running to keep the preview alive. Ctrl+C to stop.")
        # Keep the process alive so the served preview stays up.
        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            return 0
    print(f"\n❌ Build failed: {outcome.error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
