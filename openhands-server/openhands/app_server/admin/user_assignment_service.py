"""Service for managing admin-controlled user assignments.

Stores assignments in the Supabase `user_assignments` table.
Each row maps a user to a locked-in model, base URL, API key,
and optional GitHub token/repo restriction.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

_logger = logging.getLogger(__name__)

TABLE_NAME = 'user_assignments'

_supabase_client = None


def _get_supabase():
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client

        url = os.environ.get('SUPABASE_URL')
        if not url:
            return None
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
        if not key:
            return None
        _supabase_client = create_client(url, key)
    return _supabase_client


class UserAssignment(BaseModel):
    user_id: str = Field(..., description='Supabase user UUID')
    email: str = Field('', description='User email for display')
    model: str = Field(..., description='Locked model slug (e.g. openai/qwen3.6-35b-a3b)')
    base_url: str = Field('', description='API base URL')
    api_key: str = Field('', description='API key (stored in plaintext; encrypted at rest by Supabase)')
    github_token: str = Field('', description='GitHub token for git operations')
    assigned_repo: str = Field('', description='Optional repo restriction (e.g. org/repo)')
    is_active: bool = Field(True, description='Whether this assignment is currently enforced')


def get_assignment(user_id: str) -> UserAssignment | None:
    supabase = _get_supabase()
    if supabase is None:
        return None
    try:
        result = (
            supabase.table(TABLE_NAME)
            .select('*')
            .eq('user_id', user_id)
            .limit(1)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return UserAssignment(**result.data[0])
    except Exception as e:
        _logger.warning(f'Failed to fetch assignment for {user_id}: {e}')
    return None


def set_assignment(assignment: UserAssignment) -> None:
    supabase = _get_supabase()
    if supabase is None:
        _logger.warning('Supabase not configured; cannot save assignment')
        return
    try:
        supabase.table(TABLE_NAME).upsert(
            {
                'user_id': assignment.user_id,
                'email': assignment.email,
                'model': assignment.model,
                'base_url': assignment.base_url,
                'api_key': assignment.api_key,
                'github_token': assignment.github_token,
                'assigned_repo': assignment.assigned_repo,
                'is_active': assignment.is_active,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            },
            on_conflict='user_id',
        ).execute()
    except Exception as e:
        _logger.error(f'Failed to save assignment for {assignment.user_id}: {e}')
        raise


def remove_assignment(user_id: str) -> bool:
    supabase = _get_supabase()
    if supabase is None:
        return False
    try:
        result = (
            supabase.table(TABLE_NAME)
            .delete()
            .eq('user_id', user_id)
            .execute()
        )
        return len(result.data) > 0
    except Exception as e:
        _logger.error(f'Failed to remove assignment for {user_id}: {e}')
        return False


def list_assignments() -> list[UserAssignment]:
    supabase = _get_supabase()
    if supabase is None:
        return []
    try:
        result = (
            supabase.table(TABLE_NAME)
            .select('*')
            .order('updated_at', desc=True)
            .execute()
        )
        return [UserAssignment(**row) for row in (result.data or [])]
    except Exception as e:
        _logger.warning(f'Failed to list assignments: {e}')
        return []
