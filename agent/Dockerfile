# BluHands agent service — production image. SDK packages + our tools/skills.
# NOT a fork of OpenHands (ADR-1).
#
# Lean by design (ADR-10): the heavy build work (node/npm/Playwright) runs INSIDE
# the per-build E2B sandbox, NOT in this container. This image runs the FastAPI
# control surface + agent orchestration (OpenHands SDK + LiteLLM + the E2B client).
# Multi-stage, non-root, no source bind-mounts in prod.

# ---- builder: install the package (+ optional agent extras) into a venv -----
FROM python:3.12-slim AS builder

# INSTALL_AGENT=1 pulls the heavy OpenHands SDK stack (real builds). Default 0 =
# base deps only (fastapi/uvicorn/pydantic/httpx) → fast image that runs in
# dry-run for an end-to-end smoke test. The agent extra MUST be installed with
# `uv`, not pip: pip can't resolve openhands-sdk's lmnr/opentelemetry tree.
ARG INSTALL_AGENT=0

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv
WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip uv

COPY pyproject.toml README.md ./
COPY agent ./agent
# uv resolves the openhands dep tree pip chokes on. Browsers are NOT downloaded
# here — Playwright verification runs inside the E2B sandbox.
RUN if [ "$INSTALL_AGENT" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends build-essential git \
      && rm -rf /var/lib/apt/lists/* \
      && uv pip install ".[agent]"; \
    else \
      uv pip install "."; \
    fi

# ---- runtime: minimal, non-root --------------------------------------------
FROM python:3.12-slim AS runtime

# Repeat the build arg so the runtime stage can react to it.
ARG INSTALL_AGENT=0

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGENT_HOST=0.0.0.0 \
    AGENT_PORT=8100 \
    AGENT_DRY_RUN=true \
    AGENT_SANDBOX_PROVIDER=local

# For REAL builds in LOCAL sandbox mode the agent runs npm/git IN THIS CONTAINER,
# so it needs Node + git. (In e2b mode the build toolchain lives in the sandbox
# template instead, but having node/git here is harmless and enables local mode.)
RUN if [ "$INSTALL_AGENT" = "1" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends curl git ca-certificates \
      && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
      && apt-get install -y --no-install-recommends nodejs \
      && apt-get clean && rm -rf /var/lib/apt/lists/*; \
    fi

# Non-root runtime user.
RUN groupadd --gid 10001 agent && useradd --uid 10001 --gid agent --create-home agent

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=agent:agent agent ./agent
COPY --chown=agent:agent server.py ./server.py
COPY --chown=agent:agent pyproject.toml README.md ./

USER agent
EXPOSE 8100

# Liveness: hit the service's own /health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.getenv('AGENT_PORT','8100')+'/health').status==200 else 1)"

CMD ["python", "server.py"]
