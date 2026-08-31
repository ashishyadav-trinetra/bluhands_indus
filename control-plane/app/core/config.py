"""Application configuration via pydantic-settings.

Single source of truth for all configuration. No ``os.environ.get`` scattered
through the codebase (working rule: configuration via pydantic-settings).
Secrets are read from the environment / secrets manager, never hardcoded.
"""

from __future__ import annotations

import enum
from functools import lru_cache
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, enum.Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class PaymentProvider(str, enum.Enum):
    """Supported payment providers (Strategy selection)."""

    STRIPE = "stripe"
    RAZORPAY = "razorpay"


class Settings(BaseSettings):
    """Typed application settings, loaded from env vars prefixed ``FORGE_``."""

    model_config = SettingsConfigDict(
        env_prefix="FORGE_",
        env_file=(".env", ".env.development"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    env: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    app_name: str = "forge"

    # --- CORS ---
    # Stored as a comma-separated string to avoid pydantic-settings JSON-decoding
    # a list env var. Use ``cors_origins`` (computed) for the parsed list.
    cors_origins_csv: str = ""

    # --- Database ---
    database_url: str = "postgresql+asyncpg://forge:forge@localhost:5432/forge"
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- JWT (RS256) ---
    jwt_private_key: str | None = None
    jwt_public_key: str | None = None
    jwt_private_key_path: Path | None = None
    jwt_public_key_path: Path | None = None
    jwt_issuer: str = "forge"
    jwt_audience: str = "forge-clients"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 1_209_600

    # --- Storage (S3-compatible) ---
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str = "forge-artifacts"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_signed_url_ttl_seconds: int = 900

    # --- Google Sign-In (OIDC authorization-code + PKCE) ---
    # Configured at console.cloud.google.com → Credentials → OAuth 2.0 Client ID
    # (type: Web application). Leave unset to hide the Google button.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    # Must match an Authorized redirect URI on the Google client, exactly.
    google_redirect_uri: str = "http://localhost:8080/api/v1/auth/oauth/google/callback"
    # Where to send the browser after the callback completes.
    frontend_base_url: str = "http://localhost:3300"

    # --- Payments ---
    payment_provider: PaymentProvider = PaymentProvider.STRIPE
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None

    # --- Credits ---
    free_credits_on_signup: int = 100
    build_credit_cost: int = 10
    credit_price_minor: int = 100  # smallest currency unit per 1 credit (e.g. paise)
    default_currency: str = "INR"

    # --- Rate limiting ---
    rate_limit_default_per_min: int = 100
    # Credential endpoints (login/register) are throttled per client IP. Tight by
    # design: this is the brute-force boundary Supabase used to cover for us.
    auth_rate_limit_per_ip: int = 10
    auth_rate_limit_window_seconds: int = 300

    # --- Nango (integration auth layer) ---
    nango_secret_key: str | None = None          # FORGE_NANGO_SECRET_KEY
    nango_base_url: str = "https://api.nango.dev"
    nango_webhook_secret: str | None = None      # FORGE_NANGO_WEBHOOK_SECRET (optional HMAC verify)

    # --- BluHands agent service (T-A01) ---
    agent_mode: str = "stub"  # stub | http
    agent_base_url: str = "http://bluhands-agent:8100"
    agent_timeout_seconds: int = 30

    # --- Domain / Entri (T-A04) ---
    # Get credentials from https://entri.com/dashboard → Applications.
    entri_api_key: str | None = None   # FORGE_ENTRI_API_KEY
    entri_app_id: str = "bluhands"     # FORGE_ENTRI_APP_ID
    entri_api_url: str = "https://api.entri.com"
    # DNS records the agent's deployed storefront needs.  These are written into
    # the "add these records" table and passed to the Entri DNS-connect widget.
    platform_a_record: str = "76.76.21.21"
    platform_cname: str = "cname.bluhands.app"
    platform_subdomain_suffix: str = "bluhands.app"

    # --- Per-role LLM gating (control-plane chooses the model by the user's role) ---
    # Placeholders — set the real values via env (FORGE_MODEL_TESTER / FORGE_MODEL_SELF).
    model_default: str = "openrouter/anthropic/claude-sonnet-4.5"
    model_tester: str = "openrouter/minimax/minimax-01"  # tester role: one fixed model
    model_self: str = "openai/qwen3.6-35b-a3b"  # internal staff: self-hosted Qwen (vLLM)
    selfhosted_domains: str = "trinetralabs.ai"


    # --- GitHub integration (via Nango) ---
    # The Nango provider_config_key for GitHub (must match your Nango dashboard).
    nango_github_provider_key: str = "github"

    # --- Observability ---
    sentry_dsn: str | None = None
    prometheus_enabled: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        """Parsed list of allowed CORS origins (from the CSV setting)."""
        return [item.strip() for item in self.cors_origins_csv.split(",") if item.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        """True in the production environment (enables strict guards)."""
        return self.env is Environment.PRODUCTION

    def model_for_role(self, role: str) -> str:
        """Return the LLM model string the agent should use for a platform role."""
        return {
            "tester": self.model_tester,
            "self": self.model_self,
        }.get(role, self.model_default)

    def resolve_jwt_private_key(self) -> str:
        """Return the RS256 private key PEM, from inline value or file path.

        Raises:
            RuntimeError: if no private key is configured.
        """
        return self._resolve_key(self.jwt_private_key, self.jwt_private_key_path, "private")

    def resolve_jwt_public_key(self) -> str:
        """Return the RS256 public key PEM, from inline value or file path.

        Raises:
            RuntimeError: if no public key is configured.
        """
        return self._resolve_key(self.jwt_public_key, self.jwt_public_key_path, "public")

    @staticmethod
    def _resolve_key(inline: str | None, path: Path | None, label: str) -> str:
        if inline:
            return inline
        if path:
            key_path = Path(path)
            if not key_path.exists():
                raise RuntimeError(f"JWT {label} key file not found: {key_path}")
            return key_path.read_text(encoding="utf-8")
        raise RuntimeError(
            f"JWT {label} key is not configured. Set FORGE_JWT_{label.upper()}_KEY "
            f"or FORGE_JWT_{label.upper()}_KEY_PATH."
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (one parse per process)."""
    return Settings()
