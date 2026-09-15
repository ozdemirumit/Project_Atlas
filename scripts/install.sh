#!/usr/bin/env bash
# Builds and starts Project Atlas (backend, frontend) as plain background processes. No Docker,
# no containers, no YAML.
#
# Usage:
#   scripts/install.sh
#
# uv, pnpm, and (on macOS/Debian/Ubuntu) PostgreSQL + pgvector are installed automatically if
# missing, asking for confirmation before any system-wide/sudo step. See README.md for what is
# and isn't auto-installable on your platform.
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

mkdir -p "$RUNTIME_DIR"

# --- prerequisites: install uv/pnpm automatically (user-local, no admin needed); install
# PostgreSQL + pgvector automatically where a safe, official package-manager path exists ---

JUST_INSTALLED_PG=0

ensure_uv() {
    command -v uv >/dev/null 2>&1 && return 0
    log "uv not found; installing it with the official installer (user-local, no admin required)."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    command -v uv >/dev/null 2>&1 \
        || fail "uv installation failed. Install it manually: https://docs.astral.sh/uv/getting-started/installation/"
}

ensure_pnpm() {
    command -v pnpm >/dev/null 2>&1 && return 0
    log "pnpm not found; installing it with the official installer (user-local, no admin required)."
    curl -fsSL https://get.pnpm.io/install.sh | sh -
    export PNPM_HOME="$HOME/.local/share/pnpm"
    export PATH="$PNPM_HOME:$PATH"
    command -v pnpm >/dev/null 2>&1 \
        || fail "pnpm installation failed. Install it manually: https://pnpm.io/installation"
}

ensure_postgresql() {
    command -v psql >/dev/null 2>&1 && return 0
    log "PostgreSQL (psql) not found."
    local os
    os="$(uname -s)"
    if [ "$os" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
        read -r -p "Install PostgreSQL 18 + pgvector with Homebrew now? Requires 'brew install postgresql@18 pgvector'. [y/N] " CONFIRM
        [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ] \
            || fail "PostgreSQL is required. Install it yourself -- see README.md -- then re-run."
        brew install postgresql@18 pgvector
        brew services start postgresql@18
        export PATH="$(brew --prefix postgresql@18)/bin:$PATH"
        JUST_INSTALLED_PG="brew"
    elif [ "$os" = "Linux" ] && command -v apt-get >/dev/null 2>&1; then
        read -r -p "Install PostgreSQL 18 + pgvector with apt now? Uses the official PGDG repository and needs sudo. [y/N] " CONFIRM
        [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ] \
            || fail "PostgreSQL is required. Install it yourself -- see README.md -- then re-run."
        sudo apt-get update
        sudo apt-get install -y postgresql-common curl ca-certificates
        sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
        sudo apt-get install -y postgresql-18 postgresql-18-pgvector
        sudo systemctl enable --now postgresql
        JUST_INSTALLED_PG="apt"
    else
        fail "Could not auto-install PostgreSQL on this system. Install PostgreSQL (with pgvector) yourself -- see README.md for platform-specific instructions -- then re-run."
    fi
    command -v psql >/dev/null 2>&1 \
        || fail "PostgreSQL installation finished but 'psql' is still not on PATH. Open a new shell and re-run."

    log "Waiting for PostgreSQL to accept connections."
    for _ in $(seq 1 15); do
        pg_isready -q >/dev/null 2>&1 && break
        sleep 1
    done
}

ensure_uv
ensure_pnpm
ensure_postgresql

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

bootstrap_atlas_role() {
    # $1: a function name that runs `psql` as a PostgreSQL superuser, given the SQL on stdin
    # or via -c, e.g. `run_as_superuser -c "..."`.
    local run_as_superuser="$1"

    # psql interpolates :'var' only for script/stdin input, never for -c: per its own docs, a -c
    # command "must be ... completely parsable by the server (i.e., it contains no psql-specific
    # features)". (A dollar-quoted DO block also fails, separately, since :'var' isn't
    # interpolated inside a quoted SQL literal such as $$ ... $$.) Check role existence
    # separately, then pipe the CREATE/ALTER statement in via stdin, where :'pw' interpolates
    # correctly.
    local role_exists
    role_exists="$("$run_as_superuser" -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'atlas'")"
    local role_verb="CREATE"
    [ -n "$role_exists" ] && role_verb="ALTER"
    echo "$role_verb ROLE atlas WITH LOGIN PASSWORD :'pw'" | \
        "$run_as_superuser" -v ON_ERROR_STOP=1 -v pw="$ATLAS_POSTGRES_PASSWORD"

    local db_exists
    db_exists="$("$run_as_superuser" -tAc "SELECT 1 FROM pg_database WHERE datname = 'atlas'")"
    if [ -z "$db_exists" ]; then
        log "Creating database 'atlas'."
        "$run_as_superuser" -v ON_ERROR_STOP=1 -c "CREATE DATABASE atlas OWNER atlas"
    fi

    log "Enabling the pgvector extension (requires pgvector to already be installed on this PostgreSQL server)."
    "$run_as_superuser" -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS vector" \
        || fail "Could not create the pgvector extension. Install pgvector on this PostgreSQL server first -- see README.md."
}

if PGPASSWORD="$ATLAS_POSTGRES_PASSWORD" psql -h "$ATLAS_POSTGRES_HOST" -p "$ATLAS_POSTGRES_PORT" \
    -U atlas -d atlas -c "SELECT 1" >/dev/null 2>&1; then
    log "Database already reachable as the atlas role; skipping superuser setup."
elif [ "$JUST_INSTALLED_PG" = "apt" ]; then
    log "Bootstrapping the atlas role/database via the postgres OS account (local, no password needed)."
    run_as_local_superuser() { sudo -u postgres psql -d postgres "$@"; }
    bootstrap_atlas_role run_as_local_superuser
elif [ "$JUST_INSTALLED_PG" = "brew" ]; then
    log "Bootstrapping the atlas role/database as the local Homebrew PostgreSQL superuser (local, no password needed)."
    run_as_local_superuser() { psql -U "$(whoami)" -d postgres "$@"; }
    bootstrap_atlas_role run_as_local_superuser
else
    log "Database not reachable as the atlas role yet. One-time setup needs your PostgreSQL superuser credentials."
    read -r -p "PostgreSQL superuser name [postgres]: " SU_USER
    SU_USER="${SU_USER:-postgres}"
    read -r -s -p "PostgreSQL superuser password: " SU_PASSWORD
    echo

    export PGPASSWORD="$SU_PASSWORD"
    run_as_remote_superuser() {
        psql -h "$ATLAS_POSTGRES_HOST" -p "$ATLAS_POSTGRES_PORT" -U "$SU_USER" -d postgres "$@"
    }
    bootstrap_atlas_role run_as_remote_superuser
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
