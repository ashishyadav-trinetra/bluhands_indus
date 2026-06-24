"""Workspace preparation for a build (pure file ops, testable offline).

Copies the golden starter into the sandbox workspace and writes the storefront's
env so it points at the tenant's Medusa backend. The agent then edits this
workspace; the Playwright verify tool runs against the built preview.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# Never copy build artifacts / deps into the fresh workspace.
_IGNORE = shutil.ignore_patterns("node_modules", ".next", ".git", "dist", "out")


def prepare_workspace(
    *,
    workspace: Path | str,
    starter_dir: Path | str,
    medusa_url: str,
    publishable_key: str = "",
) -> Path:
    """Copy the starter into ``workspace`` and write ``.env.local``.

    Returns the workspace path.

    Raises:
        FileNotFoundError: if the starter directory does not exist.
    """
    workspace = Path(workspace)
    starter_dir = Path(starter_dir)
    if not starter_dir.is_dir():
        raise FileNotFoundError(f"starter not found: {starter_dir}")

    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(starter_dir, workspace, dirs_exist_ok=True, ignore=_IGNORE)

    env = (
        f"NEXT_PUBLIC_MEDUSA_URL={medusa_url}\n"
        f"NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY={publishable_key}\n"
    )
    (workspace / ".env.local").write_text(env, encoding="utf-8")
    return workspace
