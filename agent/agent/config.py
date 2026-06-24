"""Agent service configuration (pydantic-settings).

All config via env (prefix ``AGENT_``) — no scattered os.environ. The LLM is
OpenRouter via LiteLLM (the OpenHands SDK's LLM layer speaks LiteLLM).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings for the BluHands agent service."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM (OpenRouter via LiteLLM) ---
    # Note: OpenRouter key uses its own conventional env var name, not AGENT_-prefixed.
    # OpenRouter slug (litellm needs the `openrouter/` prefix). Override via
    # AGENT_LLM_MODEL. Old `claude-3.5-sonnet` is retired on OpenRouter.
    llm_model: str = "openrouter/anthropic/claude-sonnet-4.5"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8100

    # --- Build execution ---
    # When True (default, and whenever no OpenRouter key is present) the service
    # runs the DryRunRunner — no LLM/network — so it works offline and in CI.
    dry_run: bool = True
    workspace_root: Path = Path("/tmp/bluhands-builds")
    preview_base_url: str = "https://preview.bluhands.dev"
    # Host used to FORM the preview URL (e.g. a LAN IP or proxy host). The server
    # still binds 127.0.0.1; empty means use the bind host in the URL.
    preview_public_host: str = ""

    # --- Sandbox (ADR-10) ---
    # Where each build executes. `local` = dev (temp dir, no isolation); `e2b` =
    # prod (one isolated ephemeral microVM per build). NEVER docker-in-docker.
    sandbox_provider: str = "local"
    e2b_template: str = "bluhands-node"  # prebuilt template with Node/npm (see e2b/)
    sandbox_timeout: int = 900  # seconds; sandbox auto-kills after this
    sandbox_workdir: str = "/home/user/app"

    # Backpressure: max concurrent builds per replica (each holds a sandbox + LLM
    # spend). Over this, POST /builds returns 429 and the control-plane queue retries.
    max_concurrent_builds: int = 4

    # Deployment environment. When "production", the agent refuses the unisolated
    # LocalSandbox (see agent.sandbox.get_sandbox_provider).
    env: str = "development"

    # Redis URL for durable job-status storage (optional).
    # When set, JobStore persists to Redis so build status survives agent restarts.
    # When unset, falls back to in-memory (fine for local dev / CI).
    redis_url: str | None = None

    # --- Build inputs ---
    # Path to the golden starter that is copied into each build sandbox.
    # None means the runner will error with a clear message if a real build is attempted.
    starter_dir: Path | None = None

    def openrouter_api_key(self) -> str | None:
        """Read the OpenRouter key from its conventional env var."""
        import os

        return os.getenv("OPENROUTER_API_KEY")

    def e2b_api_key(self) -> str | None:
        """Read the E2B key from its conventional env var (used in prod)."""
        import os

        return os.getenv("E2B_API_KEY")

    def use_real_runner(self) -> bool:
        """Real OpenHands runner only when explicitly enabled AND a key exists."""
        return (not self.dry_run) and bool(self.openrouter_api_key())


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
