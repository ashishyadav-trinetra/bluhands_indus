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

# git + curl + wget for tooling; Node 22 for the process-sandbox runtime.
RUN apt-get update && apt-get install -y --no-install-recommends git curl wget \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g pnpm \
 && rm -f /usr/bin/npm /usr/bin/npx \
 && ln -s $(which pnpm) /usr/bin/npm \
 && ln -s $(which pnpm) /usr/bin/npx \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── openvscode-server (the "Code" tab) ───────────────────────────────────────
# The agent-server starts VS Code itself on boot, but only if the binary is at
# this EXACT path — VSCodeService hardcodes `Path("/openhands/.openvscode-server")`
# and silently disables VS Code when it's missing ("VSCode server binary not
# found"), which is why the tab has always said "URL not available" under
# RUNTIME=process. Same release + layout the upstream agent-server image uses.
ARG OPENVSCODE_RELEASE_TAG="openvscode-server-v1.98.2"
ENV OPENVSCODE_SERVER_ROOT=/openhands/.openvscode-server
RUN set -eux; \
    mkdir -p "$(dirname ${OPENVSCODE_SERVER_ROOT})"; \
    arch="$(uname -m)"; \
    if [ "${arch}" = "x86_64" ]; then arch="x64"; \
    elif [ "${arch}" = "aarch64" ]; then arch="arm64"; \
    elif [ "${arch}" = "armv7l" ]; then arch="armhf"; fi; \
    wget -q "https://github.com/gitpod-io/openvscode-server/releases/download/${OPENVSCODE_RELEASE_TAG}/${OPENVSCODE_RELEASE_TAG}-linux-${arch}.tar.gz"; \
    tar -xzf "${OPENVSCODE_RELEASE_TAG}-linux-${arch}.tar.gz"; \
    rm -rf "${OPENVSCODE_SERVER_ROOT}"; \
    mv "${OPENVSCODE_RELEASE_TAG}-linux-${arch}" "${OPENVSCODE_SERVER_ROOT}"; \
    cp "${OPENVSCODE_SERVER_ROOT}/bin/remote-cli/openvscode-server" \
       "${OPENVSCODE_SERVER_ROOT}/bin/remote-cli/code"; \
    rm -f "${OPENVSCODE_RELEASE_TAG}-linux-${arch}.tar.gz"

RUN pip install --no-cache-dir uv

# Install ONLY the locked dependencies (not the project itself). This avoids
# building the openhands-ai wheel, whose poetry-dynamic-versioning backend would
# need git version tags at build time. The package is imported from source below
# via PYTHONPATH instead.
COPY pyproject.toml uv.lock ./
RUN touch README.md && uv sync --frozen --no-dev --no-install-project

# The Supabase-backed per-user settings/secrets stores import the `supabase`
# client, which isn't in the base lockfile. Without it, every settings SAVE
# raises (500) while reads degrade silently. Install it into the venv.
RUN uv pip install --python /app/.venv/bin/python supabase

# The default agent preset includes a browser tool that requires Chromium at
# conversation startup (otherwise creating a conversation 500s). Install Chromium
# + its OS dependencies into the venv's Playwright.
RUN /app/.venv/bin/python -m playwright install --with-deps chromium

# App source + config + microagents/skills.
COPY openhands/ ./openhands/
COPY config.toml ./
COPY .openhands/ ./.openhands/

# httpx User-Agent patch — loaded automatically by Python's site module
# in EVERY process (parent + subprocess sandboxes) to bypass Cloudflare WAF.
COPY patches/ /app/patches/

ENV PYTHONPATH=/app/patches:/app \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    SERVE_FRONTEND=false

EXPOSE 3000

# Use the venv's uvicorn directly; openhands is importable from /app via PYTHONPATH.
CMD ["/app/.venv/bin/uvicorn", "openhands.server.listen:app", "--host", "0.0.0.0", "--port", "3000"]
