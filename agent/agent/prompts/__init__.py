"""Load agent prompt files from this directory."""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).parent


def load_base_prompt() -> str:
    """Return the base system prompt from base_system_prompt.md.

    Returns an empty string if the file is missing or still contains the
    placeholder marker — callers fall back to their own default.
    """
    path = _DIR / "base_system_prompt.md"
    if not path.is_file():
        return ""
    content = path.read_text(encoding="utf-8").strip()
    if "PLACEHOLDER" in content:
        return ""
    return content
