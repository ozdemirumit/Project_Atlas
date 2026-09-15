#!/usr/bin/env bash
# Builds and starts Project Atlas (backend, frontend) as plain background processes against a
# PostgreSQL server you install yourself. No Docker, no containers, no YAML.
#
# Usage:
#   scripts/install.sh
#
# Prerequisites: PostgreSQL (with the pgvector extension available), uv, pnpm. See README.md.
# Idempotent: re-running rebuilds dependencies and restarts the backend/frontend processes
# without touching existing database data. Run scripts/uninstall.sh to stop everything.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
ENV_EXAMPLE="$REPO_ROOT/.env.example"
RUNTIME_DIR="$REPO_ROOT/.atlas"

BACKEND_PORT=8000
FRONTEND_PORT=5173

log() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nError: %s\n' "$1" >&2; exit 1; }

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command '$1' is not available. See README.md for prerequisites."
}

require_command uv
require_command pnpm
require_command psql

mkdir -p "$RUNTIME_DIR"

# --- .env: create it from .env.example with a freshly generated database password ---

if [ ! -f "$ENV_FILE" ]; then
    log "No .env found; creating one from .env.example with a generated database password."
    [ -f "$ENV_EXAMPLE" ] || fail ".env.example is missing; cannot generate .env."
    if command -v openssl >/dev/null 2>&1; then
        GENERATED_PASSWORD="$(openssl rand -hex 32)"
    else
        GENERATED_PASSWORD="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    fi
    sed "s/^ATLAS_POSTGRES_PASSWORD=.*/ATLAS_POSTGRES_PASSWORD=${GENERATED_PASSWORD}/" \
        "$ENV_EXAMPLE" > "$ENV_FILE"
    log "Created .env with a generated ATLAS_POSTGRES_PASSWORD. Keep this file private; it is already gitignored."
else
    log "Using existing .env."
fi

# .env can hold values that are not valid bash syntax on their own (JSON arrays, LDAP filter
# strings with unescaped parentheses, ...), so it must not be `source`d as a script.
get_env_value() {
    grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d '=' -f2-
}

ATLAS_POSTGRES_PASSWORD="$(get_env_value ATLAS_POSTGRES_PASSWORD)"
ATLAS_POSTGRES_HOST="$(get_env_value ATLAS_POSTGRES_HOST)"
ATLAS_POSTGRES_PORT="$(get_env_value ATLAS_POSTGRES_PORT)"
: "${ATLAS_POSTGRES_HOST:=localhost}"
: "${ATLAS_POSTGRES_PORT:=5432}"

[ -n "$ATLAS_POSTGRES_PASSWORD" ] || fail "ATLAS_POSTGRES_PASSWORD is not set in .env."
if [ "$ATLAS_POSTGRES_PASSWORD" = "replace-with-a-local-development-secret" ]; then
    fail "ATLAS_POSTGRES_PASSWORD in .env is still the placeholder value. Set a real secret and re-run."
fi

# --- database: create the atlas role/database/extension only if they are not already usable ---

if PGPASSWORD="$ATLAS_POSTGRES_PASSWORD" psql -h "$ATLAS_POSTGRES_HOST" -p "$ATLAS_POSTGRES_PORT" \
    -U atlas -d atlas -c "SELECT 1" >/dev/null 2>&1; then
    log "Database already reachable as the atlas role; skipping superuser setup."
else
    log "Database not reachable as the atlas role yet. One-time setup needs your PostgreSQL superuser credentials."
    read -r -p "PostgreSQL superuser name [postgres]: " SU_USER
    SU_USER="${SU_USER:-postgres}"
    read -r -s -p "PostgreSQL superuser password: " SU_PASSWORD
    echo

    export PGPASSWORD="$SU_PASSWORD"

    psql -h "$ATLAS_POSTGRES_HOST" -p "$ATLAS_POSTGRES_PORT" -U "$SU_USER" -d postgres \
        -v ON_ERROR_STOP=1 -v pw="$ATLAS_POSTGRES_PASSWORD" <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'atlas') THEN
        EXECUTE format('CREATE ROLE atlas WITH LOGIN PASSWORD %L', :'pw');
    ELSE
        EXECUTE format('ALTER ROLE atlas WITH LOGIN PASSWORD %L', :'pw');
    END IF;
END
$$;
SQL

    DB_EXISTS="$(psql -h "$ATLAS_POSTGRES_HOST" -p "$ATLAS_POSTGRES_PORT" -U "$SU_USER" -d postgres \
        -tAc "SELECT 1 FROM pg_database WHERE datname = 'atlas'")"
    if [ -z "$DB_EXISTS" ]; then
        log "Creating database 'atlas'."
        psql -h "$ATLAS_POSTGRES_HOST" -p "$ATLAS_POSTGRES_PORT" -U "$SU_USER" -d postgres \
            -v ON_ERROR_STOP=1 -c "CREATE DATABASE atlas OWNER atlas"
    fi

    log "Enabling the pgvector extension (requires pgvector to already be installed on this PostgreSQL server)."
    psql -h "$ATLAS_POSTGRES_HOST" -p "$ATLAS_POSTGRES_PORT" -U "$SU_USER" -d atlas \
        -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS vector" \
        || fail "Could not create the pgvector extension. Install pgvector on this PostgreSQL server first -- see README.md."

    unset PGPASSWORD
    unset SU_PASSWORD
fi

ATLAS_DATABASE_URL="postgresql+psycopg://atlas:${ATLAS_POSTGRES_PASSWORD}@${ATLAS_POSTGRES_HOST}:${ATLAS_POSTGRES_PORT}/atlas"

# --- backend: install dependencies and run migrations ---

log "Installing backend dependencies."
(cd "$REPO_ROOT/backend" && uv sync --frozen)

log "Running database migrations."
(cd "$REPO_ROOT/backend" && ATLAS_DATABASE_URL="$ATLAS_DATABASE_URL" uv run alembic upgrade head)

# --- frontend: install dependencies ---

log "Installing frontend dependencies."
(cd "$REPO_ROOT/frontend" && pnpm install --frozen-lockfile)

# --- start backend + frontend as background processes ---

wait_for_http() {
    local url="$1" attempts="${2:-30}" delay="${3:-2}"
    local i
    for ((i = 1; i <= attempts; i++)); do
        curl -fsS "$url" >/dev/null 2>&1 && return 0
        sleep "$delay"
    done
    return 1
}

stop_if_running() {
    local pidfile="$1"
    [ -f "$pidfile" ] || return 0
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" >/dev/null 2>&1; then
        kill "$pid" >/dev/null 2>&1 || true
        sleep 1
        kill -0 "$pid" >/dev/null 2>&1 && kill -9 "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "$pidfile"
}

log "Starting the backend on port $BACKEND_PORT."
stop_if_running "$RUNTIME_DIR/backend.pid"
(
    cd "$REPO_ROOT/backend"
    ATLAS_ENVIRONMENT=development \
    ATLAS_DATABASE_REQUIRED=true \
    ATLAS_DATABASE_URL="$ATLAS_DATABASE_URL" \
    ATLAS_DEVELOPMENT_IDENTITY_ENABLED=true \
        nohup uv run uvicorn atlas.main:app --app-dir src --host 0.0.0.0 --port "$BACKEND_PORT" \
        > "$RUNTIME_DIR/backend.log" 2>&1 &
    echo $! > "$RUNTIME_DIR/backend.pid"
)

log "Waiting for the backend to become healthy."
wait_for_http "http://127.0.0.1:${BACKEND_PORT}/health/ready" 30 2 \
    || fail "Backend did not become healthy in time. Check: $RUNTIME_DIR/backend.log"

log "Starting the frontend on port $FRONTEND_PORT."
stop_if_running "$RUNTIME_DIR/frontend.pid"
(
    cd "$REPO_ROOT/frontend"
    ATLAS_API_PROXY_TARGET="http://127.0.0.1:${BACKEND_PORT}" \
        nohup pnpm dev --host 0.0.0.0 --port "$FRONTEND_PORT" \
        > "$RUNTIME_DIR/frontend.log" 2>&1 &
    echo $! > "$RUNTIME_DIR/frontend.pid"
)

log "Waiting for the frontend to become available."
wait_for_http "http://127.0.0.1:${FRONTEND_PORT}/" 30 2 \
    || fail "Frontend did not become available in time. Check: $RUNTIME_DIR/frontend.log"

cat <<EOF

Project Atlas is running.

  Web application: http://localhost:${FRONTEND_PORT}
  API:              http://localhost:${BACKEND_PORT}
  API docs:         http://localhost:${BACKEND_PORT}/docs

Stop everything with: scripts/uninstall.sh
View logs with: tail -f $RUNTIME_DIR/backend.log $RUNTIME_DIR/frontend.log
EOF
