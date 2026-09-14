#!/usr/bin/env bash
# Builds and starts Project Atlas (database, backend, frontend) as plain Docker containers.
# No Docker Compose, no YAML -- everything here is imperative `docker build`/`docker run`.
#
# Usage:
#   scripts/install.sh
#
# Idempotent: re-running rebuilds the images and replaces any existing Atlas containers.
# Run scripts/uninstall.sh to stop and remove everything this script creates.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
ENV_EXAMPLE="$REPO_ROOT/.env.example"

NETWORK_NAME="atlas-network"
VOLUME_NAME="atlas-postgres-data"
DATABASE_CONTAINER="atlas-database"
BACKEND_CONTAINER="atlas-backend"
FRONTEND_CONTAINER="atlas-frontend"
DATABASE_IMAGE="pgvector/pgvector:pg18"
BACKEND_IMAGE="atlas-backend:local"
FRONTEND_IMAGE="atlas-frontend:local"

log() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nError: %s\n' "$1" >&2; exit 1; }

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command '$1' is not available. See README.md for prerequisites."
}

require_command docker
docker info >/dev/null 2>&1 || fail "Docker does not appear to be running. Start Docker and try again."

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

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

[ -n "${ATLAS_POSTGRES_PASSWORD:-}" ] || fail "ATLAS_POSTGRES_PASSWORD is not set in .env."
if [ "$ATLAS_POSTGRES_PASSWORD" = "replace-with-a-local-development-secret" ]; then
    fail "ATLAS_POSTGRES_PASSWORD in .env is still the placeholder value. Set a real secret and re-run."
fi

# --- network + volume (idempotent) ---

docker network inspect "$NETWORK_NAME" >/dev/null 2>&1 || {
    log "Creating Docker network '$NETWORK_NAME'."
    docker network create "$NETWORK_NAME" >/dev/null
}

docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1 || {
    log "Creating Docker volume '$VOLUME_NAME'."
    docker volume create "$VOLUME_NAME" >/dev/null
}

remove_if_exists() {
    docker rm -f "$1" >/dev/null 2>&1 || true
}

wait_for_healthy() {
    local container="$1" attempts="${2:-30}" delay="${3:-2}"
    local i status
    for ((i = 1; i <= attempts; i++)); do
        status="$(docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "unknown")"
        [ "$status" = "healthy" ] && return 0
        [ "$status" = "unhealthy" ] && fail "$container reported unhealthy. Check: docker logs $container"
        sleep "$delay"
    done
    fail "$container did not become healthy in time. Check: docker logs $container"
}

# --- database ---

log "Starting PostgreSQL ($DATABASE_CONTAINER)."
remove_if_exists "$DATABASE_CONTAINER"
docker run -d \
    --name "$DATABASE_CONTAINER" \
    --network "$NETWORK_NAME" \
    --restart unless-stopped \
    -e POSTGRES_DB=atlas \
    -e POSTGRES_USER=atlas \
    -e POSTGRES_PASSWORD="$ATLAS_POSTGRES_PASSWORD" \
    -v "$VOLUME_NAME:/var/lib/postgresql/data" \
    --health-cmd="pg_isready -U atlas -d atlas" \
    --health-interval=5s \
    --health-timeout=3s \
    --health-retries=10 \
    --health-start-period=10s \
    "$DATABASE_IMAGE" >/dev/null

log "Waiting for PostgreSQL to become healthy."
wait_for_healthy "$DATABASE_CONTAINER" 30 2

# --- backend ---

log "Building the backend image."
docker build -t "$BACKEND_IMAGE" "$REPO_ROOT/backend"

log "Starting the backend ($BACKEND_CONTAINER)."
remove_if_exists "$BACKEND_CONTAINER"
docker run -d \
    --name "$BACKEND_CONTAINER" \
    --network "$NETWORK_NAME" \
    --restart unless-stopped \
    -e ATLAS_ENVIRONMENT=development \
    -e ATLAS_DATABASE_REQUIRED=true \
    -e ATLAS_DATABASE_URL="postgresql+psycopg://atlas:${ATLAS_POSTGRES_PASSWORD}@${DATABASE_CONTAINER}:5432/atlas" \
    -e ATLAS_DEVELOPMENT_IDENTITY_ENABLED=true \
    -p 127.0.0.1:8000:8000 \
    --health-cmd="python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=2)\"" \
    --health-interval=10s \
    --health-timeout=3s \
    --health-retries=6 \
    --health-start-period=15s \
    --entrypoint sh \
    "$BACKEND_IMAGE" \
    -c "uv run --no-dev alembic upgrade head && uv run --no-dev uvicorn atlas.main:app --app-dir src --host 0.0.0.0 --port 8000" >/dev/null

log "Waiting for the backend to become healthy (this runs the database migrations)."
wait_for_healthy "$BACKEND_CONTAINER" 30 3

# --- frontend ---

log "Building the frontend image."
docker build -t "$FRONTEND_IMAGE" "$REPO_ROOT/frontend"

log "Starting the frontend ($FRONTEND_CONTAINER)."
remove_if_exists "$FRONTEND_CONTAINER"
docker run -d \
    --name "$FRONTEND_CONTAINER" \
    --network "$NETWORK_NAME" \
    --restart unless-stopped \
    -p 127.0.0.1:5173:8080 \
    "$FRONTEND_IMAGE" >/dev/null

log "Waiting for the frontend to become healthy."
wait_for_healthy "$FRONTEND_CONTAINER" 15 2

cat <<EOF

Project Atlas is running.

  Web application: http://localhost:5173
  API:              http://localhost:8000
  API docs:         http://localhost:8000/docs

Stop and remove everything with: scripts/uninstall.sh
View logs with: docker logs -f $BACKEND_CONTAINER
EOF
