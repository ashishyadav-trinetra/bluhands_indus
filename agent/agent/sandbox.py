"""Sandbox providers — where a build actually executes (Strategy pattern).

PRODUCTION REQUIREMENT (ADR-10): each client build runs in its OWN isolated,
ephemeral sandbox. Docker-in-Docker does NOT scale and is NOT used in prod.
Instead we depend on a sandbox *service* that provisions a fresh microVM/container
per build and tears it down after. The selected prod provider is **E2B** (gVisor
isolation, fast cold starts, per-build kill). The provider is swappable behind the
``SandboxProvider`` / ``SandboxSession`` interfaces so the runner code is
provider-agnostic — scale is the sandbox service + a queue/autoscaler, never one
fat host running DinD.

- ``LocalSandbox``  : dev only — a local temp dir + local subprocesses. No isolation.
- ``E2BSandbox``    : prod — one isolated ephemeral E2B sandbox per build.

Both yield a ``SandboxSession`` exposing exactly the ops a build needs: run a
command, read/write files, upload the golden starter, start the preview server in
the background, resolve a public preview URL, and close (destroy) the sandbox.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ExecResult:
    """Result of running one command in a sandbox."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class SandboxSession(Protocol):
    """A live, acquired sandbox for exactly one build. Destroyed on ``close``."""

    sandbox_id: str
    workdir: str  # absolute path inside the sandbox where the app lives

    async def run(
        self,
        cmd: str,
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult: ...

    async def write_file(self, path: str, data: str) -> None: ...

    async def read_file(self, path: str) -> str: ...

    async def upload_dir(self, local_dir: str | Path, dest: str | None = None) -> None: ...

    async def start_background(
        self, cmd: str, *, cwd: str | None = None, env: dict[str, str] | None = None
    ) -> None: ...

    async def preview_url(self, port: int) -> str: ...

    async def close(self) -> None: ...


class SandboxProvider(Protocol):
    """Provisions an isolated, ephemeral build sandbox."""

    async def acquire(self, build_id: str) -> SandboxSession:
        """Create and return a fresh sandbox for one build."""
        ...


# --------------------------------------------------------------------------- #
# Local (dev) — no isolation
# --------------------------------------------------------------------------- #

class LocalSandboxSession:
    """DEV ONLY: a local temp dir + local subprocesses. Never use in prod."""

    def __init__(
        self,
        build_id: str,
        root: Path | None = None,
        *,
        public_host: str = "",
    ) -> None:
        base = str(root) if root else None
        path = Path(tempfile.mkdtemp(prefix=f"bluhands-{build_id}-", dir=base))
        self._path = path
        self._public_host = public_host  # e.g. "54.241.132.227" or "" for localhost
        self.sandbox_id = f"local-{build_id}"
        self.workdir = str(path)
        self._bg: list[asyncio.subprocess.Process] = []

    async def run(self, cmd, *, cwd=None, env=None, timeout=None) -> ExecResult:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd or self.workdir,
            env=_merge_env(env),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return ExecResult(124, "", f"timeout after {timeout}s")
        return ExecResult(proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace"))

    async def write_file(self, path: str, data: str) -> None:
        p = self._abs(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data, encoding="utf-8")

    async def read_file(self, path: str) -> str:
        return self._abs(path).read_text(encoding="utf-8")

    async def upload_dir(self, local_dir, dest=None) -> None:
        target = self._abs(dest) if dest else self._path
        shutil.copytree(local_dir, target, dirs_exist_ok=True)

    async def start_background(self, cmd, *, cwd=None, env=None) -> None:
        proc = await asyncio.create_subprocess_shell(
            cmd, cwd=cwd or self.workdir, env=_merge_env(env),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        self._bg.append(proc)

    async def preview_url(self, port: int) -> str:
        host = self._public_host or "127.0.0.1"
        return f"http://{host}:{port}"

    async def close(self) -> None:
        for proc in self._bg:
            with contextlib.suppress(Exception):
                proc.kill()
        shutil.rmtree(self._path, ignore_errors=True)

    def _abs(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else self._path / p


class LocalSandbox:
    """Dev provider: hands out local temp-dir sessions."""

    def __init__(self, root: Path | None = None, *, public_host: str = "") -> None:
        self._root = root
        self._public_host = public_host

    async def acquire(self, build_id: str) -> SandboxSession:
        return LocalSandboxSession(build_id, self._root, public_host=self._public_host)


# --------------------------------------------------------------------------- #
# E2B (prod) — isolated ephemeral microVM per build
# --------------------------------------------------------------------------- #

class E2BSandboxSession:
    """PROD: wraps one E2B ``AsyncSandbox`` (one per build)."""

    def __init__(self, sandbox, *, workdir: str) -> None:
        self._sb = sandbox
        self.sandbox_id = getattr(sandbox, "sandbox_id", "e2b")
        self.workdir = workdir

    async def run(self, cmd, *, cwd=None, env=None, timeout=None) -> ExecResult:  # pragma: no cover - needs E2B
        res = await self._sb.commands.run(
            cmd, cwd=cwd or self.workdir, envs=env or {}, timeout=timeout or 0
        )
        return ExecResult(
            getattr(res, "exit_code", 0) or 0,
            getattr(res, "stdout", "") or "",
            getattr(res, "stderr", "") or "",
        )

    async def write_file(self, path: str, data: str) -> None:  # pragma: no cover - needs E2B
        await self._sb.files.write(self._abs(path), data)

    async def read_file(self, path: str) -> str:  # pragma: no cover - needs E2B
        return await self._sb.files.read(self._abs(path))

    async def upload_dir(self, local_dir, dest=None) -> None:  # pragma: no cover - needs E2B
        # Upload every file under local_dir, preserving the relative tree.
        from e2b import WriteEntry  # type: ignore

        base = Path(local_dir)
        target_root = self._abs(dest) if dest else self.workdir
        entries: list = []
        for f in base.rglob("*"):
            if f.is_file():
                rel = f.relative_to(base).as_posix()
                entries.append(WriteEntry(path=f"{target_root}/{rel}", data=f.read_bytes()))
        if entries:
            await self._sb.files.write_files(entries)

    async def start_background(self, cmd, *, cwd=None, env=None) -> None:  # pragma: no cover - needs E2B
        await self._sb.commands.run(
            cmd, cwd=cwd or self.workdir, envs=env or {}, background=True
        )

    async def preview_url(self, port: int) -> str:  # pragma: no cover - needs E2B
        host = self._sb.get_host(port)
        if inspect.isawaitable(host):
            host = await host
        return f"https://{host}"

    async def close(self) -> None:  # pragma: no cover - needs E2B
        with contextlib.suppress(Exception):
            await self._sb.kill()

    def _abs(self, path: str) -> str:
        return path if path.startswith("/") else f"{self.workdir}/{path}"


class E2BSandbox:
    """Prod provider: one isolated, ephemeral E2B sandbox per build."""

    def __init__(
        self,
        *,
        api_key: str,
        template: str = "base",
        timeout: int = 900,
        workdir: str = "/home/user/app",
    ) -> None:
        if not api_key:
            raise RuntimeError("E2B_API_KEY is required for the E2B sandbox provider.")
        self._api_key = api_key
        self._template = template
        self._timeout = timeout
        self._workdir = workdir

    async def acquire(self, build_id: str) -> SandboxSession:  # pragma: no cover - needs E2B
        try:
            from e2b import AsyncSandbox  # type: ignore
        except ImportError as exc:
            raise RuntimeError("e2b is not installed; add the `agent` extra.") from exc

        sandbox = await AsyncSandbox.create(
            template=self._template,
            timeout=self._timeout,
            api_key=self._api_key,
            metadata={"build_id": build_id, "app": "bluhands"},
        )
        session = E2BSandboxSession(sandbox, workdir=self._workdir)
        await sandbox.commands.run(f"mkdir -p {self._workdir}")
        return session


# --------------------------------------------------------------------------- #
# Factory + helpers
# --------------------------------------------------------------------------- #

def get_sandbox_provider(settings) -> SandboxProvider:
    """Choose the sandbox provider from settings.

    ``local`` (default, dev) → ``LocalSandbox``; ``e2b`` (prod) → ``E2BSandbox``.
    """
    provider = (getattr(settings, "sandbox_provider", "local") or "local").lower()
    if provider == "e2b":
        return E2BSandbox(
            api_key=settings.e2b_api_key() or "",
            template=getattr(settings, "e2b_template", "base"),
            timeout=getattr(settings, "sandbox_timeout", 900),
            workdir=getattr(settings, "sandbox_workdir", "/home/user/app"),
        )
    if provider != "local":  # explicit, fail loud on a typo'd provider name
        raise ValueError(f"unknown sandbox_provider {provider!r} (use 'local' or 'e2b')")
    # Isolation guard: LocalSandbox shares the host kernel/FS — never in prod.
    if str(getattr(settings, "env", "development")).lower() == "production":
        raise RuntimeError(
            "Refusing LocalSandbox in production (no isolation). "
            "Set AGENT_SANDBOX_PROVIDER=e2b + E2B_API_KEY."
        )
    public_host = getattr(settings, "preview_public_host", "") or ""
    return LocalSandbox(public_host=public_host)


def _merge_env(env: dict[str, str] | None) -> dict[str, str] | None:
    if not env:
        return None
    import os

    return {**os.environ, **env}
