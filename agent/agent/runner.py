"""Build runners (Strategy pattern).

- ``DryRunRunner``: no LLM, no network — simulates the pipeline so the service
  works offline and in CI. Default whenever no OpenRouter key / dry_run is on.
- ``OpenHandsRunner``: the real thing — builds an OpenHands agent (OpenRouter
  LLM) against a workspace, then runs the Playwright verify gate. Lazy imports
  keep the SDK optional until a real build is requested.

Both implement ``BuildRunner``; the server picks one via settings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from agent.config import Settings


@dataclass(frozen=True)
class BuildSpec:
    """Everything a runner needs to execute one build.

    The first four fields are the control-plane contract; the rest are optional
    build context (manifest/brand/backend connection/starter) used by the real
    runner once available — defaults keep the basic contract + tests intact.
    """

    build_id: str
    prompt: str
    tenant_id: str
    industry: str
    manifest: dict | None = None
    brand: dict | None = None
    business: dict | None = None
    products: list[dict] | None = None
    feature_flags: list[str] | None = None
    backend_url: str | None = None
    publishable_key: str = ""
    admin_email: str = ""
    admin_password: str = ""
    starter_dir: str | None = None
    preview_port: int | None = None
    skip_agent: bool = False
    # answers to the pre-build clarification popup (list[agent.clarify.Answer])
    clarifications: list | None = None
    # enhanced/planned prompt from the PLAN step (replaces the raw one-liner)
    enhanced_prompt: str | None = None
    # LLM model override chosen by the control-plane (per-role gating); None = default
    llm_model: str | None = None
    # GitHub (user-driven; token fetched by the control-plane from Nango)
    github_repo_url: str | None = None  # https clone url of the connected repo
    github_token: str | None = None  # access token (used only inside the sandbox)
    github_branch: str = "main"
    github_push: bool = False  # push the generated code after a successful build
    github_pull: bool = False  # pull latest before building (runner generalization, 2b)


@dataclass(frozen=True)
class BuildOutcome:
    """Result of a build run."""

    success: bool
    preview_url: str | None = None
    error: str | None = None


class BuildRunner(Protocol):
    """Interface every runner implements."""

    async def run(self, spec: BuildSpec) -> BuildOutcome: ...


class DryRunRunner:
    """Offline runner: writes a marker into the workspace and reports success.

    Lets the whole control-plane → agent → status loop run end-to-end without an
    LLM, a browser, or network — ideal for dev and CI.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, spec: BuildSpec) -> BuildOutcome:
        started_at = datetime.now(timezone.utc).isoformat()
        workspace = Path(self._settings.workspace_root) / spec.build_id
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "BUILD.txt").write_text(
            f"dry-run build for tenant={spec.tenant_id} industry={spec.industry}\n"
            f"prompt:\n{spec.prompt}\n",
            encoding="utf-8",
        )
        preview = f"{self._settings.preview_base_url}/{spec.build_id}"
        outcome = BuildOutcome(success=True, preview_url=preview)
        _write_conversation_log(workspace, spec, outcome, started_at)
        return outcome


class OpenHandsRunner:
    """Live runner (T-A07 + T-A08b): the full autonomous build, sandboxed.

    Pipeline, ordered so the result is correct even if the LLM step is skipped:
      1. seed the merchant's products into Medusa  (best-effort, local HTTP)
      2. upload golden starter + write backend env  → sandbox
      3. apply the brand kit deterministically      → sandbox (computed locally, uploaded)
      4. OpenHands customises the storefront        → sandbox (graceful — never fatal)
      5. npm run build + start preview              → sandbox
      6. Playwright self-test of critical flows     (advisory, against the preview URL)

    Every step that touches the filesystem or runs a subprocess goes through
    ``SandboxSession`` (ADR-10). Provider is ``LocalSandbox`` in dev or
    ``E2BSandbox`` in prod — the runner code is provider-agnostic.

    Imports the heavy deps (OpenHands SDK, httpx, Playwright) lazily so the
    package stays importable without them.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @staticmethod
    def _log(msg: str) -> None:
        print(f"[bluhands] {msg}", flush=True)

    async def run(self, spec: BuildSpec) -> BuildOutcome:  # pragma: no cover - needs services
        from agent.sandbox import get_sandbox_provider

        started_at = datetime.now(timezone.utc).isoformat()
        provider = get_sandbox_provider(self._settings)
        session = await provider.acquire(spec.build_id)
        try:
            outcome = await self._run_in_session(spec, session)
        finally:
            await session.close()
        workspace = Path(self._settings.workspace_root) / spec.build_id
        workspace.mkdir(parents=True, exist_ok=True)
        _write_conversation_log(workspace, spec, outcome, started_at)
        return outcome

    async def _run_in_session(self, spec: BuildSpec, session) -> BuildOutcome:  # pragma: no cover
        workdir = session.workdir

        if spec.skip_agent:
            # Resume mode: workspace must already be built inside the sandbox.
            try:
                await session.read_file(f"{workdir}/package.json")
            except Exception:
                return BuildOutcome(
                    success=False,
                    error=f"--skip-agent: no built workspace at {workdir}",
                )
            self._log(f"resume mode — reusing workspace {workdir} (skipping agent)")
        elif spec.github_pull and spec.github_repo_url:
            # Build from the user's existing repo (pull latest), not the starter.
            self._log("step 1 — cloning the connected GitHub repo into the sandbox…")
            if not await self._clone_repo(spec, session):
                return BuildOutcome(success=False, error="git clone failed")
            if await self._file_exists(session, f"{workdir}/package.json"):
                self._log("  npm install in sandbox…")
                inst = await session.run("npm install", cwd=workdir, timeout=600)
                if not inst.ok:
                    self._log(f"  npm install failed (non-fatal): {inst.stderr[-300:]}")
        else:
            # 1. Seed products (local HTTP call to Medusa — not in sandbox).
            self._log("step 1/6 — seeding products into Medusa…")
            await self._seed(spec)

            # 2+3. Prepare workspace: copy starter (if any) + env + brand, then upload.
            import shutil as _shutil
            import tempfile

            if spec.starter_dir:
                self._log("step 2/6 — preparing + uploading starter to sandbox…")
                with tempfile.TemporaryDirectory(prefix=f"bluhands-{spec.build_id}-") as tmp:
                    tmp_path = Path(tmp)
                    _shutil.copytree(
                        spec.starter_dir,
                        tmp_path,
                        dirs_exist_ok=True,
                        ignore=_shutil.ignore_patterns("node_modules", ".next", ".git", "dist"),
                    )
                    # Write env from the manifest's template — industry-agnostic.
                    # Tokens: {backend_url}, {publishable_key}, {admin_email}, {admin_password}
                    _subs = {
                        "backend_url": spec.backend_url or "",
                        "publishable_key": spec.publishable_key or "",
                        "admin_email": spec.admin_email or "",
                        "admin_password": spec.admin_password or "",
                    }
                    env_template: dict[str, str] = (spec.manifest or {}).get("envTemplate", {})
                    env_lines = [
                        f"{k}={v.format(**_subs)}"
                        for k, v in env_template.items()
                        if v.format(**_subs)  # skip keys whose value resolves to empty
                    ]
                    if env_lines:
                        (tmp_path / ".env.local").write_text(
                            "\n".join(env_lines) + "\n", encoding="utf-8"
                        )

                    if spec.brand:
                        from agent.brand import apply_brand

                        self._log("step 3/6 — applying brand kit to design tokens…")
                        try:
                            apply_brand(tmp_path, spec.brand)
                        except Exception as exc:  # noqa: BLE001 - branding is best-effort
                            self._log(f"  brand apply failed (non-fatal): {exc}")

                    await session.upload_dir(str(tmp_path))

                # 3.5 npm install inside the sandbox (starter assumed npm-based).
                self._log("step 3.5 — npm install in sandbox…")
                res = await session.run("npm install", cwd=workdir, timeout=600)
                if not res.ok:
                    self._log(f"  npm install failed: {res.stderr[-400:]}")
                    return BuildOutcome(success=False, error="npm install failed")
            else:
                self._log("step 2/6 — no starter; agent will scaffold from scratch…")

            # 4. OpenHands builds the app — main act, not optional.
            self._log("step 4/6 — OpenHands building the app…")
            ok, detail = await self._customize_in_session(spec, session)
            if ok:
                self._log(f"  OpenHands finished: {detail}")
            elif self._settings.use_real_runner():
                self._log(f"  OpenHands FAILED: {detail}")
                return BuildOutcome(success=False, error=f"OpenHands build failed: {detail}")
            else:
                self._log(f"  OpenHands skipped: {detail}")

        # 5. Build + serve preview inside the sandbox.
        # Commands come from the manifest so any stack works, not just Next.js.
        _manifest = spec.manifest or {}
        preview_port = spec.preview_port or int(_manifest.get("defaultPort", 3000))
        build_cmd = _manifest.get("buildCmd", "npm run build")
        serve_cmd = _manifest.get("serveCmd", f"npm run start -- -p {preview_port} -H 0.0.0.0")
        build_timeout = int(_manifest.get("buildTimeout", 900))

        self._log(f"step 5/6 — build ({build_cmd}) + serve in sandbox…")
        build_res = await session.run(build_cmd, cwd=workdir, timeout=build_timeout)
        if not build_res.ok:
            return BuildOutcome(
                success=False,
                error=f"build failed: {build_res.stderr[-500:]}",
            )

        await session.start_background(serve_cmd, cwd=workdir)
        preview_url = await session.preview_url(preview_port)

        # 6. Self-test (advisory — a failing check is reported, not fatal).
        self._log("step 6/6 — Playwright self-test…")
        await self._self_test(spec, preview_url)

        # 7. Optional: push the generated code to the user's GitHub repo.
        await self._maybe_push(spec, session)

        return BuildOutcome(success=True, preview_url=preview_url)

    async def _clone_repo(self, spec: BuildSpec, session) -> bool:  # pragma: no cover - needs sandbox
        """Clone the user's GitHub repo into the (empty) sandbox workdir."""
        auth_url = spec.github_repo_url or ""
        if spec.github_token and auth_url.startswith("https://"):
            auth_url = auth_url.replace(
                "https://", f"https://x-access-token:{spec.github_token}@", 1
            )
        res = await session.run(f'git clone --depth 1 "{auth_url}" .', cwd=session.workdir, timeout=300)
        if not res.ok:
            self._log(f"  git clone failed: {(res.stderr or res.stdout)[-300:]}")
        return res.ok

    async def _file_exists(self, session, path: str) -> bool:  # pragma: no cover - needs sandbox
        try:
            await session.read_file(path)
            return True
        except Exception:  # noqa: BLE001
            return False

    async def _maybe_push(self, spec: BuildSpec, session) -> None:  # pragma: no cover - needs sandbox
        """Commit + push the generated code to GitHub, if the user opted in.

        Best-effort: a push failure is logged, never fails the build. The token
        is used only inside the ephemeral sandbox (destroyed right after).
        """
        if not (spec.github_push and spec.github_repo_url and spec.github_token):
            return
        self._log("step 7 — pushing generated code to GitHub…")
        branch = spec.github_branch or "main"
        auth_url = spec.github_repo_url.replace(
            "https://", f"https://x-access-token:{spec.github_token}@", 1
        )
        script = (
            "git init -q 2>/dev/null; "
            'git config user.email "agent@bluhands.dev"; '
            'git config user.name "BluHands Agent"; '
            f"git checkout -B {branch} 2>/dev/null; "
            "git add -A; "
            'git commit -q -m "BluHands build" 2>/dev/null; '
            "git remote remove origin 2>/dev/null; "
            f'git remote add origin "{auth_url}"; '
            f"git push -u origin {branch} --force"
        )
        try:
            res = await session.run(script, cwd=session.workdir, timeout=180)
            if not res.ok:
                self._log(f"  git push failed (non-fatal): {res.stderr[-300:]}")
            else:
                self._log("  pushed to GitHub.")
        except Exception as exc:  # noqa: BLE001 - push is best-effort
            self._log(f"  git push error (non-fatal): {exc}")

    async def _seed(self, spec: BuildSpec) -> None:
        from agent.seeders import run_seeder

        try:
            await run_seeder(
                spec.industry,
                backend_url=spec.backend_url,
                admin_email=spec.admin_email,
                admin_password=spec.admin_password,
                products=spec.products,
                business=spec.business,
            )
        except Exception:  # noqa: BLE001 - seeding is best-effort
            pass

    async def _customize_in_session(self, spec: BuildSpec, session) -> tuple[bool, str]:
        """Run OpenHands to build the storefront inside the sandbox. Returns (ok, detail).

        For E2B sessions the SDK is told to reuse the already-provisioned sandbox
        (``sandbox_type="e2b"`` + ``sandbox_id``), avoiding a second cold start.
        """
        import traceback

        from agent.clarify import apply_answers
        from agent.prompt import compose_build_prompt

        prompt = compose_build_prompt(
            manifest=spec.manifest or {},
            base_prompt=spec.enhanced_prompt or spec.prompt,
            brand=spec.brand,
            business=spec.business,
            products=spec.products,
            feature_flags=spec.feature_flags,
            user_request=apply_answers(spec.clarifications),
            industry=spec.industry,
        )
        try:
            await session.write_file(f"{session.workdir}/.bluhands-prompt.txt", prompt)
        except Exception:  # noqa: BLE001
            pass

        if not self._settings.openrouter_api_key():
            return (False, "OPENROUTER_API_KEY not set")

        try:
            from agent.llm import build_llm
            from openhands.sdk import Agent, Conversation, Tool  # type: ignore
            from openhands.tools.file_editor import FileEditorTool  # type: ignore
            from openhands.tools.terminal import TerminalTool  # type: ignore
        except ImportError as exc:
            return (False, f"openhands not installed: {exc}")

        try:
            model = spec.llm_model or self._settings.llm_model
            self._log(f"  model={model}; launching OpenHands agent…")
            llm = build_llm(self._settings, model=spec.llm_model)
            agent = Agent(
                llm=llm,
                tools=[Tool(name=TerminalTool.name), Tool(name=FileEditorTool.name)],
            )
            # Reuse the sandbox we already provisioned so the SDK doesn't cold-start
            # a second one. E2B sessions expose a non-local sandbox_id.
            conv_kwargs: dict = {
                "workspace": session.workdir,
                # Disable confirmation mode: removes security_risk as a required
                # tool-call field, preventing "Failed to provide security_risk"
                # validation errors when the LLM omits it.
                "confirmation_mode": False,
            }
            sandbox_id = getattr(session, "sandbox_id", None)
            if sandbox_id and not sandbox_id.startswith("local-"):
                conv_kwargs["sandbox_type"] = "e2b"
                conv_kwargs["sandbox_id"] = sandbox_id
            conversation = Conversation(agent=agent, **conv_kwargs)
            conversation.send_message(prompt)
            conversation.run()
            return (True, "agent run completed")
        except Exception as exc:  # noqa: BLE001 - surface the real reason
            tb = traceback.format_exc()
            try:
                await session.write_file(
                    f"{session.workdir}/openhands-error.log", tb
                )
            except Exception:  # noqa: BLE001
                pass
            print(tb, flush=True)
            return (False, f"{type(exc).__name__}: {exc}")

    async def _self_test(self, spec: BuildSpec, preview_url: str | None) -> None:
        if not preview_url:
            return
        flows = (spec.manifest or {}).get("criticalFlows", ["page_load"])
        try:
            from agent.tools.playwright_verify import verify

            await verify(preview_url, critical_flows=flows)
        except Exception:  # noqa: BLE001 - advisory only
            pass


def _write_conversation_log(
    workspace: Path,
    spec: BuildSpec,
    outcome: BuildOutcome,
    started_at: str,
) -> None:
    """Persist a build summary to ``{workspace}/conversation.json``.

    The file is written to the named Docker volume (``/var/bluhands-builds``) so
    it survives agent container restarts.  It is intentionally minimal — a record
    of what was asked and what happened — not a full LLM trace (those live inside
    the sandbox via ``openhands-error.log`` and ``.bluhands-prompt.txt``).
    """
    record = {
        "build_id": spec.build_id,
        "tenant_id": spec.tenant_id,
        "industry": spec.industry,
        "prompt": spec.prompt,
        "enhanced_prompt": spec.enhanced_prompt,
        "llm_model": spec.llm_model,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "success": outcome.success,
        "preview_url": outcome.preview_url,
        "error": outcome.error,
        # Placeholder for future per-step OpenHands event log.
        "steps": [],
    }
    try:
        (workspace / "conversation.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
    except OSError:
        pass  # best-effort — never crash the build over a log write


def get_runner(settings: Settings) -> BuildRunner:
    """Factory: choose the real runner only when explicitly enabled + key present."""
    if settings.use_real_runner():
        return OpenHandsRunner(settings)
    return DryRunRunner(settings)
