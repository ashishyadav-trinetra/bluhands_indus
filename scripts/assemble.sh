#!/usr/bin/env bash
# Assemble the clean Projects/bluhands monorepo (Linux/macOS/WSL).
# Idempotent. Excludes .venv, node_modules, __pycache__, .git, build artifacts.
set -euo pipefail

SDK="${SDK:-$HOME/Documents/Work/Bucket/bluhandsdk/SDK}"
OH="${OH:-$HOME/Documents/Work/Projects/OpenHands}"
DEST="${DEST:-$HOME/Documents/Work/Projects/bluhands}"

EXCLUDES=(--exclude '.venv' --exclude 'node_modules' --exclude '__pycache__'
          --exclude '.git' --exclude '.pytest_cache' --exclude '.ruff_cache'
          --exclude '.mypy_cache' --exclude 'build' --exclude 'dist'
          --exclude '.react-router' --exclude '.turbo' --exclude '.next'
          --exclude '*.pyc' --exclude '*.log')

copy_tree() {
  local src="$1" dst="$2"
  if [ ! -d "$src" ]; then echo "skip (missing): $src"; return; fi
  echo "copy: $src -> $dst"; mkdir -p "$dst"
  rsync -a --delete "${EXCLUDES[@]}" "$src/" "$dst/"
}

mkdir -p "$DEST/docs"
copy_tree "$SDK/control-plane"  "$DEST/control-plane"
copy_tree "$SDK/bluhands-agent" "$DEST/agent"
copy_tree "$SDK/apps"           "$DEST/apps"
copy_tree "$SDK/catalog"        "$DEST/backends"
copy_tree "$OH/frontend"        "$DEST/frontend"

for f in PROJECT-HANDOFF.md TASKS.md WORKLOG.md; do
  [ -f "$SDK/$f" ] && cp "$SDK/$f" "$DEST/docs/$f"
done
[ -d "$SDK/prompts" ] && copy_tree "$SDK/prompts" "$DEST/docs/prompts"

echo "Done. Clean monorepo at $DEST"
echo "Next: docs/EXTRACTION-PLAN.md -> T-A09 (wire frontend to REST backend)."
