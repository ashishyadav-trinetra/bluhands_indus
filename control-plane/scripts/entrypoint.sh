#!/bin/sh
set -e
echo "[entrypoint] Running alembic upgrade head..."
alembic upgrade head
echo "[entrypoint] Migrations applied. Starting server..."
exec "$@"
