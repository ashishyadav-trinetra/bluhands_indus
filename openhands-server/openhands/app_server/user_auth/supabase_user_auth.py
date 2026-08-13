"""Supabase-based user authentication.

Extracts user identity from Supabase JWT tokens passed in the Authorization header.
Falls back to DefaultUserAuth behavior (no auth) when no token is present,
allowing gradual migration.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import jwt
from fastapi import Request
from pydantic import SecretStr

from openhands.app_server.admin.user_assignment_service import get_assignment
from openhands.app_server.integrations.provider import PROVIDER_TOKEN_TYPE
from openhands.app_server.secrets.secrets_models import Secrets
from openhands.app_server.secrets.secrets_store import SecretsStore
from openhands.app_server.settings.settings_models import Settings
from openhands.app_server.settings.settings_store import SettingsStore
from openhands.app_server.user_auth.user_auth import UserAuth
from openhands.server import shared

_logger = logging.getLogger(__name__)


_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    """Cache one PyJWKClient so we don't refetch the JWKS on every request."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def _decode_supabase_token(token: str) -> dict | None:
    """Decode and verify a Supabase JWT.

    Supports BOTH schemes Supabase uses, picked from the token's own ``alg``:
    - **HS256** with the project's shared secret (``SUPABASE_JWT_SECRET``), and
    - **asymmetric ES256/RS256** verified via the project's JWKS endpoint
      (``SUPABASE_JWKS_URL``, or derived from ``SUPABASE_URL``).

    Newer Supabase projects sign **ES256**; the original HS256-only code silently
    failed on those and collapsed every user to 'default' (the multi-tenancy bug).
    """
    try:
        alg = jwt.get_unverified_header(token).get('alg', '')
    except Exception:  # noqa: BLE001 - malformed token
        return None

    try:
        if alg == 'HS256':
            secret = os.getenv('SUPABASE_JWT_SECRET')
            if not secret:
                _logger.warning('SUPABASE_JWT_SECRET not set; cannot verify HS256 token')
                return None
            return jwt.decode(
                token,
                secret,
                algorithms=['HS256'],
                audience='authenticated',
                options={'verify_exp': True},
            )

        if alg == 'RS256':
            forge_key_path = os.getenv('FORGE_JWT_PUBLIC_KEY_PATH')
            if forge_key_path:
                try:
                    with open(forge_key_path, 'r') as f:
                        public_key = f.read()
                    return jwt.decode(
                        token,
                        public_key,
                        algorithms=['RS256'],
                        audience='forge-clients',
                        issuer='forge',
                        options={'verify_exp': True},
                    )
                except Exception as e:
                    _logger.warning(f'Failed to verify Forge JWT: {e}')
                    return None

        # Asymmetric (ES256 / RS256) → verify against the project's JWKS.
        jwks_url = os.getenv('SUPABASE_JWKS_URL')
        if not jwks_url:
            base = os.getenv('SUPABASE_URL', '').rstrip('/')
            jwks_url = f'{base}/auth/v1/.well-known/jwks.json' if base else None
        if not jwks_url:
            _logger.warning(
                'No SUPABASE_JWKS_URL/SUPABASE_URL set; cannot verify %s token', alg
            )
            return None
        signing_key = _get_jwks_client(jwks_url).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=['ES256', 'RS256'],
            audience='authenticated',
            options={'verify_exp': True},
        )
    except jwt.ExpiredSignatureError:
        _logger.debug('Supabase token expired')
        return None
    except jwt.InvalidTokenError as e:
        _logger.debug(f'Invalid Supabase token: {e}')
        return None
    except Exception as e:  # noqa: BLE001 - JWKS fetch / key resolution errors
        _logger.debug(f'Supabase token verification error: {e}')
        return None


def _is_platform_admin(email: str | None) -> bool:
    """True when this user's email is in BLUHANDS_ADMIN_EMAILS (comma-separated)."""
    raw = os.getenv('BLUHANDS_ADMIN_EMAILS', '')
    e = (email or '').strip().lower()
    if not e:
        return False
    return e in {a.strip().lower() for a in raw.split(',') if a.strip()}


def _platform_llm_diff() -> dict | None:
    """The settings *diff* that grafts the PLATFORM model + key onto a user's
    settings. Returns None if the platform model/key env isn't configured."""
    model = os.getenv('BLUHANDS_PLATFORM_LLM_MODEL')
    api_key = os.getenv('BLUHANDS_PLATFORM_LLM_API_KEY')
    if not (model and api_key):
        return None
    return {
        'agent_settings_diff': {
            'llm': {
                'model': model,
                'api_key': api_key,
                'base_url': os.getenv(
                    'BLUHANDS_PLATFORM_LLM_BASE_URL',
                    'https://openrouter.ai/api/v1',
                ),
            }
        }
    }


# ── Step-budget caps for the self-hosted box ─────────────────────────────────
# qwen3.6-35b-a3b is a *thinking* model and the box decodes at ~32 tok/s. The
# SDK defaults (max_output_tokens=64000, reasoning_effort='high') let a single
# agent step generate for 64000/32 = ~33 minutes, while llm.timeout is 300s — so
# every step died with litellm.Timeout and was retried num_retries=5 times, i.e.
# the agent sat on step 0 for ~30 minutes and never advanced. Three independent
# brakes, cheapest first:
#
# 1. Hard cap the step. 4096 tok / 32 tok/s = ~128s, which fits inside the 300s
#    timeout even after a 52k-token prefill (measured: 16s). This one works on
#    ANY provider and is the real safety net.
# 2. Ask for less reasoning via the first-class LiteLLM field.
# 3. Turn qwen's thinking block off outright. Measured against the vLLM box:
#    reasoning output 0 chars and tool calls still emitted correctly (7026 -> 74
#    output tokens on the same prompt). Unknown chat_template_kwargs are ignored
#    by templates that don't declare them, so this is inert on non-qwen models.
#
# max_input_tokens: the box serves max_model_len=262144; the SDK default of
# 1000000 means the condenser never fires before the server rejects the request
# outright. Leave room for the output cap.
_SELFHOSTED_STEP_CAPS: dict = {
    'max_output_tokens': 4096,
    'reasoning_effort': 'low',
    'litellm_extra_body': {'chat_template_kwargs': {'enable_thinking': False}},
    'max_input_tokens': 200000,
}


def _is_selfhosted_user(email: str | None) -> bool:
    """True when this user's email domain is in BLUHANDS_SELFHOSTED_DOMAINS.

    This decides who gets *seeded* with the self-hosted model. It must NOT be
    used to decide who gets the step caps — see _runs_on_selfhosted_box.
    """
    domains = os.getenv('BLUHANDS_SELFHOSTED_DOMAINS', '')
    domain = (email or '').strip().lower().rsplit('@', 1)[-1]
    if not (domains and domain):
        return False
    return domain in {d.strip().lower() for d in domains.split(',') if d.strip()}


def _with_platform_git_token(user_secrets: Secrets | None) -> Secrets | None:
    """Graft the platform's org-wide GitHub token onto a user's secrets.

    Set BLUHANDS_GITHUB_TOKEN to give every user the repo picker and in-sandbox
    clone/push/PR without each of them connecting their own account. Optionally
    set BLUHANDS_GITHUB_HOST for GitHub Enterprise.

    Use a PERSONAL ACCESS TOKEN (classic or fine-grained), not a GitHub App
    installation token: installation tokens expire after one hour, and this is
    read from a static env var with no refresh, so it would silently stop
    working. If you want App-based auth it needs a token-minting step, which
    this does not do.

    This exists because the normal route — Settings -> Integrations -> paste a
    PAT — is unreachable for the users who need it most: non-admin
    @<selfhosted-domain> users have the whole Settings page hidden, so they can
    never connect a repo at all.

    A token the user connected THEMSELVES always wins; this only fills the gap.
    """
    token = os.getenv('BLUHANDS_GITHUB_TOKEN', '').strip()
    if not token:
        return user_secrets

    try:
        from types import MappingProxyType

        from openhands.app_server.integrations.provider import (
            ProviderToken,
            ProviderType,
        )

        if user_secrets is None:
            user_secrets = Secrets()

        existing = dict(user_secrets.provider_tokens or {})
        current = existing.get(ProviderType.GITHUB)
        if current is not None and current.token:
            return user_secrets  # user's own connection wins

        host = os.getenv('BLUHANDS_GITHUB_HOST', '').strip() or None
        existing[ProviderType.GITHUB] = ProviderToken(
            token=SecretStr(token),
            host=host,
        )
        return user_secrets.model_copy(
            update={'provider_tokens': MappingProxyType(existing)}
        )
    except Exception:  # noqa: BLE001 - never break auth over an optional token
        _logger.warning('Failed to apply platform GitHub token', exc_info=True)
        return user_secrets


def _runs_on_selfhosted_box(settings) -> bool:
    """True when the RESOLVED LLM actually targets the self-hosted endpoint.

    Keyed on the endpoint, not the person. Gating the caps on email was wrong:
    platform admins are excluded from the self-hosted *seed* (they get the
    OpenRouter model instead), but an admin who points their settings at the
    box by hand is running the same slow thinking model as everyone else and
    needs the same step budget. Checking the endpoint covers every route onto
    the box — seeded users, admin assignments, and manual Settings edits.
    """
    base_url = os.getenv('BLUHANDS_SELFHOSTED_BASE_URL')
    if settings is None or not base_url:
        return False
    try:
        resolved = settings.agent_settings.llm.base_url
    except AttributeError:
        return False
    if not resolved:
        return False
    return str(resolved).rstrip('/') == base_url.rstrip('/')


def _selfhosted_llm_diff(email: str | None) -> dict | None:
    """Settings diff for the org's SELF-HOSTED model (e.g. Qwen on the DGX box).

    Applied to users whose email domain is in BLUHANDS_SELFHOSTED_DOMAINS — they
    build on the self-hosted endpoint with NO external key and NO upgrade.
    BLUHANDS_SELFHOSTED_MODEL is a full LiteLLM slug (e.g. 'openai/Qwen3-32B' or
    'hosted_vllm/qwen'); BLUHANDS_SELFHOSTED_BASE_URL is the OpenAI-compatible
    endpoint (e.g. http://192.168.1.50:8000/v1). The api_key is a dummy because
    LiteLLM requires a non-empty value even when the server ignores it.
    """
    base_url = os.getenv('BLUHANDS_SELFHOSTED_BASE_URL')
    model = os.getenv('BLUHANDS_SELFHOSTED_MODEL')
    if not (base_url and model):
        return None
    if not _is_selfhosted_user(email):
        return None
    # Force LiteLLM's OpenAI-compatible CHAT path. Without a provider prefix
    # (or with a 'custom/' one) LiteLLM falls into a text-completion path that
    # does `" ".join(message["content"])` and crashes on structured/list content
    # ("expected str instance, list found"). Prepending openai/ keeps it a chat
    # model that posts to {base_url}/chat/completions with the messages intact.
    if not model.startswith(('openai/', 'hosted_vllm/', 'litellm_proxy/')):
        model = f'openai/{model}'
    return {
        'agent_settings_diff': {
            'llm': {
                'model': model,
                'base_url': base_url,
                'api_key': os.getenv('BLUHANDS_SELFHOSTED_API_KEY', 'sk-local'),
                **_SELFHOSTED_STEP_CAPS,
            }
        }
    }


@dataclass
class SupabaseUserAuth(UserAuth):
    """Supabase-based user authentication.

    Extracts user_id and email from Supabase JWT tokens.
    When no valid token is present, falls back to 'default' user
    for backward compatibility during migration.
    """

    _user_id: str | None = field(default=None, repr=False)
    _user_email: str | None = field(default=None, repr=False)
    _settings: Settings | None = field(default=None, repr=False)
    _settings_store: SettingsStore | None = field(default=None, repr=False)
    _secrets_store: SecretsStore | None = field(default=None, repr=False)
    _secrets: Secrets | None = field(default=None, repr=False)

    async def get_user_id(self) -> str | None:
        return self._user_id

    async def get_user_email(self) -> str | None:
        return self._user_email

    async def get_access_token(self) -> SecretStr | None:
        return None

    async def get_user_settings_store(self) -> SettingsStore:
        settings_store = self._settings_store
        if settings_store:
            return settings_store
        user_id = await self.get_user_id()
        settings_store = await shared.SettingsStoreImpl.get_instance(
            shared.config, user_id
        )
        if settings_store is None:
            raise ValueError('Failed to get settings store instance')
        self._settings_store = settings_store
        return settings_store

    async def get_user_settings(self) -> Settings | None:
        settings = self._settings
        if settings:
            settings.email = self._user_email
            return settings
        settings_store = await self.get_user_settings_store()
        settings = await settings_store.load()
            
        has_key = settings is not None and bool(
            getattr(settings, 'llm_api_key_is_set', False)
        )
        is_admin = _is_platform_admin(self._user_email)

        # BluHands tiers:
        #
        # * Non-admin @<selfhosted-domain> users are PINNED to the self-hosted
        #   model — it is seeded for them AND re-applied on every read, so it
        #   cannot be changed. The UI hides the Settings page for these users,
        #   but that is cosmetic: POST /api/v1/settings stays reachable, so the
        #   pin has to be enforced server-side on read or the model can drift
        #   (and then never gets corrected, because the seed below only ever
        #   fired when no key was stored).
        # * Platform admins are NOT pinned — they build on the company
        #   OpenRouter model, or bring their own provider/key, and may change it
        #   freely. Their model is only seeded when they have none yet.
        # * Everyone else gets nothing → they must upgrade, and can never use
        #   the company key.
        pinned_diff = None if is_admin else _selfhosted_llm_diff(self._user_email)

        if pinned_diff is not None:
            if settings is None:
                settings = Settings()
            settings.update(pinned_diff)
            # Persist only on first seed; re-pins are in-memory so we don't
            # write to the settings store on every request.
            if not has_key:
                try:
                    await settings_store.store(settings)
                except Exception:  # noqa: BLE001 - seeding is best-effort
                    pass
        elif not has_key and is_admin:
            diff = _platform_llm_diff()
            if diff is not None:
                if settings is None:
                    settings = Settings()
                settings.update(diff)
                try:
                    await settings_store.store(settings)
                except Exception:  # noqa: BLE001 - seeding is best-effort
                    pass
        # BluHands admin assignment: if an active assignment exists, it overrides
        # the user's model/repo settings entirely (locked).
        # BluHands admin assignment: if an active assignment exists, it overrides
        # the user's model/repo settings entirely (locked).
        if self._user_id:
            assignment = get_assignment(self._user_id)
            if assignment and assignment.is_active:
                llm_diff = {
                    'agent_settings_diff': {
                        'llm': {
                            'model': assignment.model,
                            'base_url': assignment.base_url,
                            'api_key': assignment.api_key,
                        }
                    }
                }
                if settings is None:
                    settings = Settings()
                settings.update(llm_diff)
        # Apply the step caps LAST, after every path that can pick a model
        # (seed, admin assignment, manual Settings edit), and gate them on the
        # resolved endpoint rather than on the user. Re-applied on every read,
        # not just at seed time: users whose settings predate these caps already
        # have an LLM key stored, so the `if not has_key` seed above never runs
        # for them. In memory only — no store write, so this stays cheap.
        if _runs_on_selfhosted_box(settings):
            settings.update(
                {'agent_settings_diff': {'llm': dict(_SELFHOSTED_STEP_CAPS)}}
            )
        if settings is None:
            settings = Settings()
        
        settings.email = self._user_email
            
        self._settings = settings
        return settings

    async def get_secrets_store(self) -> SecretsStore:
        secrets_store = self._secrets_store
        if secrets_store:
            return secrets_store
        user_id = await self.get_user_id()
        secret_store = await shared.SecretsStoreImpl.get_instance(
            shared.config, user_id
        )
        if secret_store is None:
            raise ValueError('Failed to get secrets store instance')
        self._secrets_store = secret_store
        return secret_store

    async def get_secrets(self) -> Secrets | None:
        user_secrets = self._secrets
        if user_secrets:
            return user_secrets
        secrets_store = await self.get_secrets_store()
        user_secrets = await secrets_store.load()
        user_secrets = _with_platform_git_token(user_secrets)
        self._secrets = user_secrets
        return user_secrets

    async def get_provider_tokens(self) -> PROVIDER_TOKEN_TYPE | None:
        user_secrets = await self.get_secrets()
        if user_secrets is None:
            return None
        return user_secrets.provider_tokens

    async def get_mcp_api_key(self) -> str | None:
        return None

    @classmethod
    async def get_instance(cls, request: Request) -> UserAuth:
        """Extract user from Supabase JWT in Authorization header."""
        user_id = None
        user_email = None

        # Try to extract token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            payload = _decode_supabase_token(token)
            if payload:
                user_id = payload.get('sub')  # Supabase user UUID
                user_email = payload.get('email')
                _logger.debug(f'Authenticated Supabase user: {user_email} ({user_id})')

        # Fall back to 'default' for unauthenticated requests (backward compat)
        if not user_id:
            user_id = 'default'

        return SupabaseUserAuth(
            _user_id=user_id,
            _user_email=user_email,
        )

    @classmethod
    async def get_for_user(cls, user_id: str) -> UserAuth:
        return SupabaseUserAuth(_user_id=user_id)
