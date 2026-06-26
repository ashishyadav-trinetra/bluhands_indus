"""Supabase Postgres-backed event storage.

Stores conversation events as JSONB in a `conversation_events` table.
Replaces FilesystemEventService for Supabase deployments.
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Request

from openhands.agent_server.models import EventPage, EventSortOrder
from openhands.app_server.event.event_service import EventService, EventServiceInjector
from openhands.app_server.event_callback.event_callback_models import EventKind
from openhands.app_server.services.injector import InjectorState
from openhands.sdk import Event

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


TABLE_NAME = 'conversation_events'


@dataclass
class SupabaseEventService(EventService):
    """Event service backed by Supabase Postgres."""

    user_id: str | None = None

    async def get_event(self, conversation_id: UUID, event_id: UUID) -> Event | None:
        try:
            supabase = _get_supabase()
            result = (
                supabase.table(TABLE_NAME)
                .select('event_json')
                .eq('conversation_id', str(conversation_id))
                .eq('event_id', str(event_id))
                .maybe_single()
                .execute()
            )
            if result.data and result.data.get('event_json'):
                return Event.model_validate(result.data['event_json'])
            return None
        except Exception as e:
            _logger.error(f'Error loading event {event_id}: {e}')
            return None

    async def search_events(
        self,
        conversation_id: UUID,
        kind__eq: EventKind | None = None,
        timestamp__gte: datetime | None = None,
        timestamp__lt: datetime | None = None,
        sort_order: EventSortOrder = EventSortOrder.TIMESTAMP,
        page_id: str | None = None,
        limit: int = 100,
    ) -> EventPage:
        try:
            supabase = _get_supabase()
            query = (
                supabase.table(TABLE_NAME)
                .select('event_json')
                .eq('conversation_id', str(conversation_id))
            )

            if kind__eq:
                query = query.eq('event_kind', kind__eq)

            if timestamp__gte:
                query = query.gte('event_timestamp', timestamp__gte.isoformat())

            if timestamp__lt:
                query = query.lt('event_timestamp', timestamp__lt.isoformat())

            # Sorting
            ascending = sort_order != EventSortOrder.TIMESTAMP_DESC
            query = query.order('event_timestamp', desc=not ascending)

            # Pagination
            start_offset = 0
            if page_id:
                start_offset = int(page_id)
                query = query.range(start_offset, start_offset + limit)
            else:
                query = query.range(0, limit)

            result = query.execute()

            items = []
            for row in result.data or []:
                try:
                    event = Event.model_validate(row['event_json'])
                    items.append(event)
                except Exception:
                    continue

            next_page_id = None
            if len(items) >= limit:
                next_page_id = str(start_offset + limit)

            return EventPage(items=items, next_page_id=next_page_id)
        except Exception as e:
            _logger.error(f'Error searching events for {conversation_id}: {e}')
            return EventPage(items=[], next_page_id=None)

    async def count_events(
        self,
        conversation_id: UUID,
        kind__eq: EventKind | None = None,
        timestamp__gte: datetime | None = None,
        timestamp__lt: datetime | None = None,
    ) -> int:
        try:
            supabase = _get_supabase()
            query = (
                supabase.table(TABLE_NAME)
                .select('event_id', count='exact')
                .eq('conversation_id', str(conversation_id))
            )

            if kind__eq:
                query = query.eq('event_kind', kind__eq)
            if timestamp__gte:
                query = query.gte('event_timestamp', timestamp__gte.isoformat())
            if timestamp__lt:
                query = query.lt('event_timestamp', timestamp__lt.isoformat())

            result = query.execute()
            return result.count or 0
        except Exception as e:
            _logger.error(f'Error counting events: {e}')
            return 0

    async def save_event(self, conversation_id: UUID, event: Event):
        try:
            supabase = _get_supabase()
            event_dict = event.model_dump(mode='python')

            # Extract searchable fields
            event_kind = event.kind if hasattr(event, 'kind') else None
            event_timestamp = None
            if hasattr(event, 'timestamp') and event.timestamp:
                event_timestamp = (
                    event.timestamp.isoformat()
                    if isinstance(event.timestamp, datetime)
                    else str(event.timestamp)
                )

            supabase.table(TABLE_NAME).upsert(
                {
                    'conversation_id': str(conversation_id),
                    'event_id': str(event.id),
                    'event_kind': event_kind,
                    'event_timestamp': event_timestamp,
                    'event_json': event_dict,
                    'user_id': self.user_id,
                },
                on_conflict='conversation_id,event_id',
            ).execute()
        except Exception as e:
            _logger.error(f'Error saving event {event.id}: {e}', exc_info=True)
            raise


class SupabaseEventServiceInjector(EventServiceInjector):
    async def inject(
        self, state: InjectorState, request: Request | None = None
    ) -> AsyncGenerator[EventService, None]:
        from openhands.app_server.config import get_user_context

        async with get_user_context(state, request) as user_context:
            user_id = await user_context.get_user_id()
            yield SupabaseEventService(user_id=user_id)
