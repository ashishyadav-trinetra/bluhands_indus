#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# BluHands server deploy — pull latest and rebuild ONLY what changed.
#
# Run by CI (GitHub Actions over SSH) on every push to main, or manually:
#   cd ~/var/www/bluhands_indus && bash scripts/deploy.sh
#
# Safe to run repeatedly. Protects the server's local .env edits (real secrets
# diverge from the tracked templates) via --autostash.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root (this script lives in scripts/)

log() { echo "[deploy $(date +%H:%M:%S)] $*"; }

BEFORE=$(git rev-parse HEAD)
log "current commit $BEFORE"

# Pull latest. autostash stashes the server's local (tracked) .env edits, pulls,
# then reapplies — so secrets aren't clobbered. A genuine conflict fails loudly
# instead of silently overwriting.
git fetch --quiet origin main
git -c rebase.autoStash=true pull --rebase --quiet origin main

AFTER=$(git rev-parse HEAD)
if [ "$BEFORE" = "$AFTER" ]; then
  log "already up to date — nothing to deploy"
  exit 0
fi
log "updated to $AFTER"

CHANGED=$(git diff --name-only "$BEFORE" "$AFTER")
echo "$CHANGED" | sed 's/^/  changed: /'
changed() { echo "$CHANGED" | grep -qE "$1"; }

# 1) Host nginx routing. Needs passwordless sudo for cp + nginx (see CICD-SETUP).
if changed '^deploy/nginx-host\.conf$'; then
  log "nginx: updating host config + reload"
  sudo cp deploy/nginx-host.conf /etc/nginx/sites-available/bluhands
  sudo nginx -t && sudo nginx -s reload
fi

# 2) App-server image — vendored code or its Dockerfile changed → rebuild.
if changed '^openhands-server/'; then
  log "openhands: build image + up"
  docker compose build openhands
  docker compose up -d openhands
fi

# 3) Compose changes (env, ports, services) — recreate to apply (no build).
#    Skipped if we already rebuilt+upped openhands above and only it changed.
if changed '^docker-compose\.yml$'; then
  log "compose: up -d (apply compose/env changes)"
  docker compose up -d
fi

# 4) Frontend — Vite bakes at build time, so a real rebuild is required.
if changed '^frontend/'; then
  log "frontend: rebuild (no-cache) + up"
  docker compose build --no-cache frontend
  docker compose up -d frontend
  log "REMINDER: purge Cloudflare cache so the new bundle is served"
fi

# 5) Control-plane (api/worker) — code is bind-mounted; up -d re-reads env_file.
if changed '^control-plane/'; then
  log "control-plane: up -d api worker"
  docker compose up -d api worker
fi

# 6) Agent service.
if changed '^agent/'; then
  log "agent: build + up"
  docker compose build agent
  docker compose up -d agent
fi

log "done — deployed $AFTER"
