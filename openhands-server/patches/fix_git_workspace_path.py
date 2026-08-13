"""Map the frontend's hardcoded /workspace/project onto the real sandbox workspace.

The Changes tab asks the agent-server for git changes at a path the FRONTEND
computes (`frontend/src/utils/get-git-path.ts`), and that path is hardcoded to
`/workspace/project[/{repo}]` — the layout of the *docker* and *remote* sandbox
images.

Under RUNTIME=process every sandbox is a subprocess of the app-server container
and its workspace is `<base_working_dir>/<sandbox_id>/workspace` instead, so the
requested path never exists. `AppConversation` exposes no working-dir field, so
the frontend cannot know the real path and cannot be fixed client-side without
an API change plus a frontend rebuild.

Result today: every Changes-tab poll raises
`GitRepositoryError: Directory does not exist: /workspace/project` and dumps a
full traceback into the agent-server log every few seconds, and the tab never
shows anything — even though the workspace IS a git repo (the app-server runs
`clone_or_init_git_repo` on it), so the changes are there to be read.

This rewrites a non-existent `/workspace/project...` request onto the sandbox's
actual workspace, preserving any repo-name suffix. Requests that already resolve
are untouched, so docker/remote runtimes keep their current behaviour exactly.

Loaded via sitecustomize.py at interpreter startup.
"""

import os
from pathlib import Path

# The path baked into the frontend and into the docker/remote sandbox specs.
_FRONTEND_PROJECT_ROOT = '/workspace/project'


def _real_workspace_root() -> Path | None:
    """The workspace directory of the agent-server running in THIS process.

    ProcessSandboxService sets AGENT_SANDBOX_DIR to the sandbox directory and
    starts the subprocess with that as its cwd; the workspace is the `workspace`
    subdirectory of it (see _create_sandbox_directory).
    """
    for base in (os.environ.get('AGENT_SANDBOX_DIR'), os.getcwd()):
        if not base:
            continue
        candidate = Path(base) / 'workspace'
        if candidate.is_dir():
            return candidate
    return None


def _remap(repo_dir):
    """Return the real path for *repo_dir*, or None to leave it alone."""
    try:
        requested = Path(repo_dir)
        if requested.exists():
            return None  # Nothing to fix — docker/remote, or an absolute hit.

        root = _real_workspace_root()
        if root is None:
            return None

        # Preserve whatever the frontend appended (a repo name, or a
        # conversation id when sandbox grouping is on).
        text = str(requested).replace('\\', '/')
        if text.startswith(_FRONTEND_PROJECT_ROOT):
            suffix = text[len(_FRONTEND_PROJECT_ROOT):].strip('/')
            if suffix:
                nested = root / suffix
                if nested.is_dir():
                    return nested
            return root
        return None
    except Exception:
        return None


def _apply_git_workspace_patches():
    try:
        from openhands.sdk.git import git_changes, git_diff, utils

        _orig_validate = utils.validate_git_repository

        def _patched_validate(repo_dir):
            remapped = _remap(repo_dir)
            return _orig_validate(remapped if remapped is not None else repo_dir)

        # git_changes and git_diff bind the function by name at import time
        # (`from openhands.sdk.git.utils import validate_git_repository`), so
        # patching only the utils module would not affect either caller.
        utils.validate_git_repository = _patched_validate
        git_changes.validate_git_repository = _patched_validate
        git_diff.validate_git_repository = _patched_validate
    except Exception:
        pass


_apply_git_workspace_patches()
