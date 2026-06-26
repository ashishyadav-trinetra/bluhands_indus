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

from openhands.app_server.integrations.provider import PROVIDER_TOKEN_TYPE
from openhands.app_server.secrets.secrets_models import Secrets
from openhands.app_server.secrets.secrets_store import SecretsStore
from openhands.app_server.settings.settings_models import Settings
from openhands.app_server.settings.settings_store import SettingsStore
from openhands.app_server.user_auth.user_auth import UserAuth
from openhands.server import shared

_logger = logging.getLogger(__name__)


def _decode_supabase_token(token: str) -> dict | None:
    """Decode and verify a Supabase JWT token."""
    jwt_secret = os.getenv('SUPABASE_JWT_SECRET')
    if not jwt_secret:
        _logger.warning('SUPABASE_JWT_SECRET not set, cannot verify tokens')
        return None
    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=['HS256'],
            audience='authenticated',
            options={'verify_exp': True},
        )
        return payload
    except jwt.ExpiredSignatureError:
        _logger.debug('Supabase token expired')
        return None
    except jwt.InvalidTokenError as e:
        _logger.debug(f'Invalid Supabase token: {e}')
        return None


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
            return settings
        settings_store = await self.get_user_settings_store()
        settings = await settings_store.load()
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
