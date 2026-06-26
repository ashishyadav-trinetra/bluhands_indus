"""Supabase Postgres-backed settings store.

Stores user settings as JSONB in a `user_settings` table in Supabase.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from openhands.app_server.settings.settings_models import Settings
from openhands.app_server.settings.settings_store import SettingsStore
from openhands.core.config.openhands_config import OpenHandsConfig

_logger = logging.getLogger(__name__)

# Lazy-initialized Supabase client
_supabase_client = None


def _get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client

        url = os.environ['SUPABASE_URL']
        # Use service_role key if available for server-side access (bypasses RLS)
        # Falls back to anon key
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_ANON_KEY']
        _supabase_client = create_client(url, key)
    return _supabase_client


TABLE_NAME = 'user_settings'


@dataclass
class SupabaseSettingsStore(SettingsStore):
    user_id: str = field(default='default')

    async def load(self) -> Settings | None:
        try:
            supabase = _get_supabase()
            result = (
                supabase.table(TABLE_NAME)
                .select('settings_json')
                .eq('user_id', self.user_id)
                .execute()
            )

            if result.data and len(result.data) > 0 and result.data[0].get('settings_json'):
                kwargs = result.data[0]['settings_json']
                if isinstance(kwargs, str):
                    kwargs = json.loads(kwargs)
                settings = Settings(**kwargs)
                settings.v1_enabled = True
                return settings
            return None
        except Exception as e:
            _logger.warning(f'Failed to load settings from Supabase: {e}')
            return None

    async def store(self, settings: Settings) -> None:
        try:
            supabase = _get_supabase()
            json_str = settings.model_dump_json(
                context={'expose_secrets': True, 'persist_settings': True}
            )
            settings_dict = json.loads(json_str)

            supabase.table(TABLE_NAME).upsert(
                {
                    'user_id': self.user_id,
                    'settings_json': settings_dict,
                },
                on_conflict='user_id',
            ).execute()
        except Exception as e:
            _logger.error(f'Failed to store settings in Supabase: {e}')
            raise

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> SupabaseSettingsStore:
        return SupabaseSettingsStore(user_id=user_id or 'default')
