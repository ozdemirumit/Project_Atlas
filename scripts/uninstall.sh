#!/usr/bin/env bash
# Stops and removes the containers and network scripts/install.sh created.
#
# Usage:
#   scripts/uninstall.sh          # stop and remove containers + network, keep the database volume
#   scripts/uninstall.sh --purge  # also delete the database volume (destroys all data)

set -euo pipefail

NETWORK_NAME="atlas-network"
VOLUME_NAME="atlas-postgres-data"
CONTAINERS=(atlas-frontend atlas-backend atlas-database)

log() { printf '\n==> %s\n' "$1"; }

for container in "${CONTAINERS[@]}"; do
    if docker inspect "$container" >/dev/null 2>&1; then
        log "Removing container $container."
        docker rm -f "$container" >/dev/null
    fi
done

if docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
    log "Removing network $NETWORK_NAME."
    docker network rm "$NETWORK_NAME" >/dev/null
fi

if [ "${1:-}" = "--purge" ]; then
    if docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
        log "Deleting volume $VOLUME_NAME (all database data will be lost)."
        docker volume rm "$VOLUME_NAME" >/dev/null
    fi
else
    log "Database volume '$VOLUME_NAME' was kept. Re-run scripts/install.sh to start again with the same data, or pass --purge to delete it."
fi

log "Project Atlas containers stopped and removed."
