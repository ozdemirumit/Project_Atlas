#!/usr/bin/env bash
# Starts the already-installed Atlas backend as a background process, without redoing dependency
# installation, PostgreSQL/pgvector setup, or database migrations -- for routine day-to-day
# process control (e.g. after a server reboot). Run scripts/install.sh first (and again after any
# code or dependency update); this script only starts what install already set up.
#
# Usage:
#   scripts/start.sh
#
# Idempotent: if the backend is already running, this prints its status and does nothing.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
RUNTIME_DIR="$REPO_ROOT/.atlas"
FRONTEND_DIST="$REPO_ROOT/frontend/dist"
BACKEND_PID_FILE="$RUNTIME_DIR/backend.pid"

BACKEND_PORT=8000

log() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nError: %s\n' "$1" >&2; exit 1; }

[ -f "$ENV_FILE" ] || fail "No .env found. Run scripts/install.sh first -- it creates .env and completes the one-time PostgreSQL/dependency setup this script assumes is already done."
[ -f "$FRONTEND_DIST/index.html" ] || fail "frontend/dist/ is missing or incomplete. Run scripts/install.sh, which checks for this."

if [ -f "$BACKEND_PID_FILE" ]; then
    EXISTING_PID="$(cat "$BACKEND_PID_FILE")"
    if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" >/dev/null 2>&1; then
        echo "Atlas backend is already running (pid $EXISTING_PID) at http://localhost:${BACKEND_PORT}"
        exit 0
    fi
    rm -f "$BACKEND_PID_FILE"
fi

get_env_value() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d '=' -f2-; }
ATLAS_POSTGRES_PASSWORD="$(get_env_value ATLAS_POSTGRES_PASSWORD)"
ATLAS_POSTGRES_HOST="$(get_env_value ATLAS_POSTGRES_HOST)"
ATLAS_POSTGRES_PORT="$(get_env_value ATLAS_POSTGRES_PORT)"
: "${ATLAS_POSTGRES_HOST:=localhost}"
: "${ATLAS_POSTGRES_PORT:=5432}"
[ -n "$ATLAS_POSTGRES_PASSWORD" ] || fail "ATLAS_POSTGRES_PASSWORD is not set in .env. Run scripts/install.sh first."
ATLAS_DATABASE_URL="postgresql+psycopg://atlas:${ATLAS_POSTGRES_PASSWORD}@${ATLAS_POSTGRES_HOST}:${ATLAS_POSTGRES_PORT}/atlas"

mkdir -p "$RUNTIME_DIR"

wait_for_http() {
    local url="$1" attempts="${2:-30}" delay="${3:-2}"
    local i
    for ((i = 1; i <= attempts; i++)); do
        curl -fsS "$url" >/dev/null 2>&1 && return 0
        sleep "$delay"
    done
    return 1
}

log "Starting the backend on port $BACKEND_PORT."
(
    cd "$REPO_ROOT/backend"
    ATLAS_ENVIRONMENT=development \
    ATLAS_DATABASE_REQUIRED=true \
    ATLAS_DATABASE_URL="$ATLAS_DATABASE_URL" \
    ATLAS_DEVELOPMENT_IDENTITY_ENABLED=true \
        nohup uv run uvicorn atlas.main:app --app-dir src --host 0.0.0.0 --port "$BACKEND_PORT" \
        > "$RUNTIME_DIR/backend.log" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
)

log "Waiting for the backend to become healthy."
wait_for_http "http://127.0.0.1:${BACKEND_PORT}/health/ready" 30 2 \
    || fail "Backend did not become healthy in time. Check: $RUNTIME_DIR/backend.log"

cat <<EOF

Project Atlas is running.

  Web application: http://localhost:${BACKEND_PORT}
  API docs:         http://localhost:${BACKEND_PORT}/docs

Stop it with: scripts/stop.sh
View logs with: tail -f $RUNTIME_DIR/backend.log
EOF
