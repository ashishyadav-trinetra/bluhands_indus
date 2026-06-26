"""SQLAlchemy Postgres-backed event storage.

Stores conversation events as JSON in the local `conversation_events` table.
Used for local/dev environments; in production the same table lives in Supabase
and SupabaseEventService is used instead.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from openhands.agent_server.models import EventPage, EventSortOrder
from openhands.app_server.event.event_service import EventService, EventServiceInjector
from openhands.app_server.event_callback.event_callback_models import EventKind
from openhands.app_server.services.injector import InjectorState
from openhands.sdk import Event

_logger = logging.getLogger(__name__)

_TABLE = 'conversation_events'

# Lightweight table reflection — no ORM model needed.
_events_table = sa.Table(
    _TABLE,
    sa.MetaData(),
    sa.Column('conversation_id', sa.String, primary_key=True),
    sa.Column('event_id', sa.String, primary_key=True),
    sa.Column('event_kind', sa.String, nullable=True),
    sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.Column('event_json', sa.JSON, nullable=False),
    sa.Column('user_id', sa.String, nullable=True),
)


@dataclass
class SqlEventService(EventService):
    """Event service backed by local Postgres via SQLAlchemy."""

    db_session: AsyncSession
    user_id: str | None = field(default=None)

    async def get_event(self, conversation_id: UUID, event_id: UUID) -> Event | None:
        try:
            stmt = sa.select(_events_table.c.event_json).where(
                _events_table.c.conversation_id == str(conversation_id),
                _events_table.c.event_id == str(event_id),
            )
            result = await self.db_session.execute(stmt)
            row = result.fetchone()
            if row and row[0]:
                return Event.model_validate(row[0])
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
            stmt = sa.select(_events_table.c.event_json).where(
                _events_table.c.conversation_id == str(conversation_id)
            )

            if kind__eq:
                stmt = stmt.where(_events_table.c.event_kind == kind__eq)
            if timestamp__gte:
                stmt = stmt.where(
                    _events_table.c.event_timestamp >= timestamp__gte
                )
            if timestamp__lt:
                stmt = stmt.where(
                    _events_table.c.event_timestamp < timestamp__lt
                )

            ascending = sort_order != EventSortOrder.TIMESTAMP_DESC
            if ascending:
                stmt = stmt.order_by(_events_table.c.event_timestamp.asc())
            else:
                stmt = stmt.order_by(_events_table.c.event_timestamp.desc())

            start_offset = int(page_id) if page_id else 0
            stmt = stmt.offset(start_offset).limit(limit + 1)

            result = await self.db_session.execute(stmt)
            rows = result.fetchall()

            items = []
            for row in rows[:limit]:
                try:
                    items.append(Event.model_validate(row[0]))
                except Exception:
                    continue

            next_page_id = None
            if len(rows) > limit:
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
            stmt = sa.select(sa.func.count()).select_from(_events_table).where(
                _events_table.c.conversation_id == str(conversation_id)
            )
            if kind__eq:
                stmt = stmt.where(_events_table.c.event_kind == kind__eq)
            if timestamp__gte:
                stmt = stmt.where(
                    _events_table.c.event_timestamp >= timestamp__gte
                )
            if timestamp__lt:
                stmt = stmt.where(
                    _events_table.c.event_timestamp < timestamp__lt
                )
            result = await self.db_session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            _logger.error(f'Error counting events: {e}')
            return 0

    async def save_event(self, conversation_id: UUID, event: Event):
        try:
            event_dict = event.model_dump(mode='python')
            event_kind = event.kind if hasattr(event, 'kind') else None
            event_timestamp = None
            if hasattr(event, 'timestamp') and event.timestamp:
                event_timestamp = (
                    event.timestamp
                    if isinstance(event.timestamp, datetime)
                    else datetime.fromisoformat(str(event.timestamp))
                )

            stmt = pg_insert(_events_table).values(
                conversation_id=str(conversation_id),
                event_id=str(event.id),
                event_kind=event_kind,
                event_timestamp=event_timestamp,
                event_json=event_dict,
                user_id=self.user_id,
            ).on_conflict_do_update(
                index_elements=['conversation_id', 'event_id'],
                set_={'event_json': event_dict, 'event_kind': event_kind},
            )
            await self.db_session.execute(stmt)
            await self.db_session.commit()
        except Exception as e:
            _logger.error(f'Error saving event {event.id}: {e}', exc_info=True)
            await self.db_session.rollback()
            raise


class SqlEventServiceInjector(EventServiceInjector):
    async def inject(
        self, state: InjectorState, request: Request | None = None
    ) -> AsyncGenerator[EventService, None]:
        from openhands.app_server.config import get_db_session, get_user_context

        async with (
            get_db_session(state, request) as db_session,
            get_user_context(state, request) as user_context,
        ):
            user_id = await user_context.get_user_id()
            yield SqlEventService(db_session=db_session, user_id=user_id)
