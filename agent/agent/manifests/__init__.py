"""Load capability manifests from this directory.

A manifest describes the backend API contract for a given industry so the agent
knows exactly which endpoints exist and what data shapes to expect.
"""

from __future__ import annotations

import json
from pathlib import Path

_DIR = Path(__file__).parent


def load_manifest(industry: str | None) -> dict:
    """Return the capability manifest for *industry*, or an empty dict if unknown."""
    name = (industry or "").lower()
    path = _DIR / f"{name}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
