from __future__ import annotations

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from openhands.app_server.app_lifespan.app_lifespan_service import AppLifespanService

_logger = logging.getLogger(__name__)


class OssAppLifespanService(AppLifespanService):
    run_alembic_on_startup: bool = True

    async def __aenter__(self):
        if self.run_alembic_on_startup:
            if os.getenv('DB_HOST'):
                # For Postgres (e.g., Supabase): use create_all to create tables
                # directly from models. Alembic migrations were written for SQLite
                # and have Postgres incompatibilities (enum types, timestamp syntax).
                self._ensure_all_tables()
                self._stamp_alembic_head()
            else:
                # For SQLite: run Alembic OSS migrations first, then call
                # create_all to catch any models (e.g. enterprise tables like
                # conversation_metadata_saas, user, org) not covered by migrations.
                self.run_alembic()
                self._ensure_all_tables()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    def _ensure_all_tables(self):
        """Create any tables not yet present using SQLAlchemy create_all.

        Uses IF NOT EXISTS semantics — safe to call on every startup.
        Imports both OSS and enterprise models so all are registered with
        Base.metadata before create_all runs.
        """
        # OSS models
        from openhands.app_server.app_conversation.sql_app_conversation_info_service import (
            StoredConversationMetadata,  # noqa: F401
        )
        from openhands.app_server.app_conversation.sql_app_conversation_start_task_service import (
            StoredAppConversationStartTask,  # noqa: F401
        )
        from openhands.app_server.event_callback.sql_event_callback_service import (
            StoredEventCallback,  # noqa: F401
            StoredEventCallbackResult,  # noqa: F401
        )
        from openhands.app_server.pending_messages.pending_message_service import (
            StoredPendingMessage,  # noqa: F401
        )
        from openhands.app_server.sandbox.remote_sandbox_service import (
            StoredRemoteSandbox,  # noqa: F401
        )
        # Enterprise models — no-op if enterprise package is not installed.
        try:
            from storage.stored_conversation_metadata_saas import (  # noqa: F401
                StoredConversationMetadataSaas,
            )
            from storage.user import User  # noqa: F401
            from storage.org import Org  # noqa: F401
        except ImportError:
            pass
        from openhands.app_server.config import get_global_config
        from openhands.app_server.utils.sql_utils import Base

        db_session_injector = get_global_config().db_session
        engine = db_session_injector.get_db_engine()
        Base.metadata.create_all(engine)
        _logger.info('All tables ensured via create_all')

    def _stamp_alembic_head(self):
        """Stamp the alembic version to head (Postgres path only)."""
        try:
            alembic_dir = Path(__file__).parent / 'alembic'
            alembic_ini = alembic_dir / 'alembic.ini'
            alembic_cfg = Config(str(alembic_ini))
            alembic_cfg.set_main_option('script_location', str(alembic_dir))
            original_cwd = os.getcwd()
            try:
                os.chdir(str(alembic_dir.parent))
                command.stamp(alembic_cfg, 'head')
            finally:
                os.chdir(original_cwd)
            _logger.info('Alembic version stamped to head')
        except Exception as e:
            _logger.warning(f'Could not stamp alembic version: {e}')

    def create_tables_from_models(self):
        """Deprecated alias kept for backward compatibility."""
        self._ensure_all_tables()
        self._stamp_alembic_head()

    def run_alembic(self):
        # Run alembic upgrade head to ensure database is up to date
        alembic_dir = Path(__file__).parent / 'alembic'
        alembic_ini = alembic_dir / 'alembic.ini'

        # Create alembic config with absolute paths
        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option('script_location', str(alembic_dir))

        # Change to alembic directory for the command execution
        original_cwd = os.getcwd()
        try:
            os.chdir(str(alembic_dir.parent))
            command.upgrade(alembic_cfg, 'head')
        finally:
            os.chdir(original_cwd)
