"""Supabase Postgres-backed secrets store.

Stores user secrets (API keys, tokens) as JSONB in a `user_secrets` table.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from openhands.app_server.secrets.secrets_models import Secrets
from openhands.app_server.secrets.secrets_store import SecretsStore
from openhands.core.config.openhands_config import OpenHandsConfig

_logger = logging.getLogger(__name__)

_supabase_client = None


def _get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client

        url = os.environ['SUPABASE_URL']
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_ANON_KEY']
        _supabase_client = create_client(url, key)
    return _supabase_client


TABLE_NAME = 'user_secrets'


@dataclass
class SupabaseSecretsStore(SecretsStore):
    user_id: str = field(default='default')

    async def load(self) -> Secrets | None:
        try:
            supabase = _get_supabase()
            result = (
                supabase.table(TABLE_NAME)
                .select('secrets_json')
                .eq('user_id', self.user_id)
                .execute()
            )

            if result.data and len(result.data) > 0 and result.data[0].get('secrets_json'):
                kwargs = result.data[0]['secrets_json']
                if isinstance(kwargs, str):
                    kwargs = json.loads(kwargs)
                provider_tokens = {
                    k: v
                    for k, v in (kwargs.get('provider_tokens') or {}).items()
                    if v.get('token')
                }
                kwargs['provider_tokens'] = provider_tokens
                return Secrets(**kwargs)
            return None
        except Exception as e:
            _logger.warning(f'Failed to load secrets from Supabase: {e}')
            return None

    async def store(self, secrets: Secrets) -> None:
        try:
            supabase = _get_supabase()
            json_str = secrets.model_dump_json(context={'expose_secrets': True})
            secrets_dict = json.loads(json_str)

            supabase.table(TABLE_NAME).upsert(
                {
                    'user_id': self.user_id,
                    'secrets_json': secrets_dict,
                },
                on_conflict='user_id',
            ).execute()
        except Exception as e:
            _logger.error(f'Failed to store secrets in Supabase: {e}')
            raise

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> SupabaseSecretsStore:
        return SupabaseSecretsStore(user_id=user_id or 'default')
