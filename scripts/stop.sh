#!/usr/bin/env bash
# Stops the backend process scripts/start.sh (or scripts/install.sh) started, without touching
# the database or any installed dependency.
#
# Usage:
#   scripts/stop.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$REPO_ROOT/.atlas"
BACKEND_PID_FILE="$RUNTIME_DIR/backend.pid"

log() { printf '\n==> %s\n' "$1"; }

if [ ! -f "$BACKEND_PID_FILE" ]; then
    log "Atlas backend is not running (no $BACKEND_PID_FILE)."
    exit 0
fi

PID="$(cat "$BACKEND_PID_FILE")"
if [ -n "$PID" ] && kill -0 "$PID" >/dev/null 2>&1; then
    log "Stopping backend (pid $PID)."
    kill "$PID" >/dev/null 2>&1 || true
    sleep 1
    kill -0 "$PID" >/dev/null 2>&1 && kill -9 "$PID" >/dev/null 2>&1 || true
else
    log "Atlas backend is not running (stale pid file)."
fi
rm -f "$BACKEND_PID_FILE"

log "Project Atlas stopped. Database data was kept; start it again with scripts/start.sh."
