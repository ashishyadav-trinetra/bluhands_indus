"""Build the storefront and serve it as a same-server preview.

`npm install` → `npm run build` → `npm run start -- -p PORT`, then the preview is
reachable at ``http://<host>:PORT``. The control plane/onboarding app shows that
URL so the merchant can see their store before publishing to a real domain.

Process handles are tracked in-module so a build can be torn down later. Each
agent build runs in its own sandbox (ADR-10), so one process map per process is
fine here; a multi-tenant preview fleet is the production concern (T-A08).
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Live preview processes by build id, so they can be stopped/replaced.
_RUNNING: dict[str, subprocess.Popen] = {}


def _exe(name: str) -> str:
    """Resolve a CLI name to a runnable path.

    On Windows, ``npm``/``npx`` are ``.cmd`` shims that ``CreateProcess`` won't
    find by bare name — ``shutil.which`` returns the full ``npm.cmd`` path.
    """
    found = shutil.which(name)
    if found:
        return found
    return f"{name}.cmd" if sys.platform == "win32" else name


@dataclass(frozen=True)
class PreviewResult:
    ok: bool
    url: str | None = None
    port: int | None = None
    logs: str = ""
    error: str | None = None


def pick_port(preferred: int | None = None) -> int:
    """Return an open TCP port (the preferred one if free, else an ephemeral)."""
    if preferred and _is_free(preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _run(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    resolved = [_exe(cmd[0]), *cmd[1:]]
    # encoding/errors: npm prints UTF-8 (emoji, ✓); Windows' default cp1252 would
    # crash the reader thread and leave stdout=None. Decode UTF-8, never fail.
    return subprocess.run(
        resolved,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def install_deps(workspace: Path | str, *, timeout: int = 600) -> tuple[bool, str]:
    """Run ``npm install`` once so the agent can build/self-check. Idempotent."""
    workspace = Path(workspace)
    if (workspace / "node_modules").is_dir():
        return (True, "node_modules present")
    res = _run(["npm", "install"], workspace, timeout)
    log = f"{res.stdout[-1500:]}\n{res.stderr[-1500:]}"
    return (res.returncode == 0, log)


def build_and_serve(
    *,
    build_id: str,
    workspace: Path | str,
    preferred_port: int | None = None,
    host: str = "127.0.0.1",
    public_host: str | None = None,
    install_timeout: int = 600,
    build_timeout: int = 900,
    ready_timeout: int = 60,
) -> PreviewResult:
    """Install deps, build, and start the Next app. Returns the preview URL.

    ``public_host`` (if set) is used to form the returned URL while the server
    still binds ``host`` locally — useful behind a reverse proxy.
    """
    workspace = Path(workspace)
    logs: list[str] = []

    install = _run(["npm", "install"], workspace, install_timeout)
    logs.append(f"$ npm install\n{(install.stdout or '')[-2000:]}\n{(install.stderr or '')[-2000:]}")
    if install.returncode != 0:
        return PreviewResult(ok=False, logs="\n".join(logs), error="npm install failed")

    build = _run(["npm", "run", "build"], workspace, build_timeout)
    logs.append(f"$ npm run build\n{(build.stdout or '')[-2000:]}\n{(build.stderr or '')[-2000:]}")
    if build.returncode != 0:
        return PreviewResult(ok=False, logs="\n".join(logs), error="next build failed")

    port = pick_port(preferred_port)
    stop(build_id)  # replace any prior preview for this build
    proc = subprocess.Popen(
        [_exe("npm"), "run", "start", "--", "-p", str(port), "-H", host],
        cwd=str(workspace),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _RUNNING[build_id] = proc

    if not _wait_until_listening(host, port, ready_timeout):
        stop(build_id)
        return PreviewResult(ok=False, logs="\n".join(logs), error="preview did not start")

    url = f"http://{public_host or host}:{port}"
    return PreviewResult(ok=True, url=url, port=port, logs="\n".join(logs))


def _wait_until_listening(host: str, port: int, timeout: int) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) == 0:
                return True
        time.sleep(1)
    return False


def stop(build_id: str) -> None:
    """Terminate a running preview, if any."""
    proc = _RUNNING.pop(build_id, None)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
