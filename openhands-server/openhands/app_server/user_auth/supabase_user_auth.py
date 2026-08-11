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


def _selfhosted_llm_diff(email: str | None) -> dict | None:
    """Settings diff for the org's SELF-HOSTED model (e.g. Qwen on the DGX box).

    Applied to users whose email domain is in BLUHANDS_SELFHOSTED_DOMAINS — they
    build on the self-hosted endpoint with NO external key and NO upgrade.
    BLUHANDS_SELFHOSTED_MODEL is a full LiteLLM slug (e.g. 'openai/Qwen3-32B' or
    'hosted_vllm/qwen'); BLUHANDS_SELFHOSTED_BASE_URL is the OpenAI-compatible
    endpoint (e.g. http://192.168.1.50:8000/v1). The api_key is a dummy because
    LiteLLM requires a non-empty value even when the server ignores it.
    """
    domains = os.getenv('BLUHANDS_SELFHOSTED_DOMAINS', '')
    base_url = os.getenv('BLUHANDS_SELFHOSTED_BASE_URL')
    model = os.getenv('BLUHANDS_SELFHOSTED_MODEL')
    if not (domains and base_url and model):
        return None
    domain = (email or '').strip().lower().rsplit('@', 1)[-1]
    allowed = {d.strip().lower() for d in domains.split(',') if d.strip()}
    if not domain or domain not in allowed:
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
            
        # BluHands: platform admins build on the company model+key. Seed it
        # whenever they have NO LLM key yet — not just when settings are absent
        # (a settings row exists after the analytics-consent save, but with no
        # LLM). Normal users get nothing → they can never use this key.
        has_key = settings is not None and bool(
            getattr(settings, 'llm_api_key_is_set', False)
        )
        if not has_key:
            # Precedence: platform admins get the OpenRouter paid model so they
            # can build with the best model. Non-admin domain-matched users get
            # the self-hosted model (Qwen). Users who are neither get nothing.
            if _is_platform_admin(self._user_email):
                diff = _platform_llm_diff()
            else:
                diff = _selfhosted_llm_diff(self._user_email)
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
