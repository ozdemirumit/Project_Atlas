#!/usr/bin/env bash
# Stops the backend process scripts/install.sh started.
#
# Usage:
#   scripts/uninstall.sh          # stop the backend, keep the database
#   scripts/uninstall.sh --purge  # also drop the atlas database and role (destroys all data)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
RUNTIME_DIR="$REPO_ROOT/.atlas"

log() { printf '\n==> %s\n' "$1"; }

stop_if_running() {
    local name="$1" pidfile="$2"
    [ -f "$pidfile" ] || return 0
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" >/dev/null 2>&1; then
        log "Stopping $name (pid $pid)."
        kill "$pid" >/dev/null 2>&1 || true
        sleep 1
        kill -0 "$pid" >/dev/null 2>&1 && kill -9 "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "$pidfile"
}

stop_if_running "backend" "$RUNTIME_DIR/backend.pid"

if [ "${1:-}" = "--purge" ]; then
    [ -f "$ENV_FILE" ] || { log "No .env found; nothing to purge."; exit 0; }

    get_env_value() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d '=' -f2-; }
    ATLAS_POSTGRES_HOST="$(get_env_value ATLAS_POSTGRES_HOST)"
    ATLAS_POSTGRES_PORT="$(get_env_value ATLAS_POSTGRES_PORT)"
    : "${ATLAS_POSTGRES_HOST:=localhost}"
    : "${ATLAS_POSTGRES_PORT:=5432}"

    log "Purging the atlas database and role (all data will be lost)."
    read -r -p "PostgreSQL superuser name [postgres]: " SU_USER
    SU_USER="${SU_USER:-postgres}"
    read -r -s -p "PostgreSQL superuser password: " SU_PASSWORD
    echo

    export PGPASSWORD="$SU_PASSWORD"
    psql -h "$ATLAS_POSTGRES_HOST" -p "$ATLAS_POSTGRES_PORT" -U "$SU_USER" -d postgres \
        -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS atlas"
    psql -h "$ATLAS_POSTGRES_HOST" -p "$ATLAS_POSTGRES_PORT" -U "$SU_USER" -d postgres \
        -v ON_ERROR_STOP=1 -c "DROP ROLE IF EXISTS atlas"
    unset PGPASSWORD
    unset SU_PASSWORD
else
    log "Database was kept. Re-run scripts/install.sh to start again with the same data, or pass --purge to delete it."
fi

log "Project Atlas stopped."
