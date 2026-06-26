# ─────────────────────────────────────────────────────────────────────────────
# BluHands OSS app-server.
#
# Vendored from the OpenHands v1 fork (openhands/app_server). Serves the
# /api/v1 routes the frontend needs — settings, agent-schema, skills, secrets,
# conversations — via `openhands.server.listen:app`. No enterprise, no billing
# (forge/control-plane owns auth+billing+admin), and no bundled frontend
# (the `frontend` service serves the UI; nginx routes /api/v1/{settings,skills,
# secrets} here).
#
# Auth runs OPEN: with SESSION_API_KEY unset and app_mode=OSS, get_dependencies()
# enforces nothing, so the settings/skills endpoints return real JSON. The
# frontend's Supabase token is simply ignored here (forge still enforces auth).
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# git + curl for tooling; Node 22 for the process-sandbox runtime (conversations).
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# Install ONLY the locked dependencies (not the project itself). This avoids
# building the openhands-ai wheel, whose poetry-dynamic-versioning backend would
# need git version tags at build time. The package is imported from source below
# via PYTHONPATH instead.
COPY pyproject.toml uv.lock ./
RUN touch README.md && uv sync --frozen --no-dev --no-install-project

# App source + config + microagents/skills.
COPY openhands/ ./openhands/
COPY config.toml ./
COPY .openhands/ ./.openhands/

ENV PYTHONPATH=/app \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    SERVE_FRONTEND=false

EXPOSE 3000

# Use the venv's uvicorn directly; openhands is importable from /app via PYTHONPATH.
CMD ["/app/.venv/bin/uvicorn", "openhands.server.listen:app", "--host", "0.0.0.0", "--port", "3000"]
