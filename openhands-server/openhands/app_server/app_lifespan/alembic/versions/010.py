"""Add conversation_events table for local Postgres event storage

Revision ID: 010
Revises: 009
Create Date: 2026-06-02 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversation_events',
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('event_kind', sa.String(), nullable=True),
        sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('event_json', sa.JSON(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('conversation_id', 'event_id'),
    )
    op.create_index(
        'ix_conversation_events_conversation_id',
        'conversation_events',
        ['conversation_id'],
    )
    op.create_index(
        'ix_conversation_events_event_timestamp',
        'conversation_events',
        ['event_timestamp'],
    )
    op.create_index(
        'ix_conversation_events_event_kind',
        'conversation_events',
        ['event_kind'],
    )


def downgrade() -> None:
    op.drop_index('ix_conversation_events_event_kind', table_name='conversation_events')
    op.drop_index(
        'ix_conversation_events_event_timestamp', table_name='conversation_events'
    )
    op.drop_index(
        'ix_conversation_events_conversation_id', table_name='conversation_events'
    )
    op.drop_table('conversation_events')
