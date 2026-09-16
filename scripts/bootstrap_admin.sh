#!/usr/bin/env bash
# Creates the first durable local administrator account (ATLAS-030 SS11 bootstrap). Run once, on
# the server, by someone with shell access -- see backend/scripts/bootstrap_admin.py for why that
# is the whole authorization model (no HTTP endpoint exists for this on purpose).
#
# Usage:
#   scripts/bootstrap_admin.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if ! command -v uv >/dev/null 2>&1; then
  echo "Required command \"uv\" is not available. See README.md for prerequisites." >&2
  exit 1
fi

[ -f "$ENV_FILE" ] || { echo "No .env found. Run scripts/install.sh first." >&2; exit 1; }

get_env_value() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d '=' -f2-; }
ATLAS_POSTGRES_PASSWORD="$(get_env_value ATLAS_POSTGRES_PASSWORD)"
ATLAS_POSTGRES_HOST="$(get_env_value ATLAS_POSTGRES_HOST)"
ATLAS_POSTGRES_PORT="$(get_env_value ATLAS_POSTGRES_PORT)"
: "${ATLAS_POSTGRES_HOST:=localhost}"
: "${ATLAS_POSTGRES_PORT:=5432}"
if [ -z "$ATLAS_POSTGRES_PASSWORD" ]; then
  echo "ATLAS_POSTGRES_PASSWORD is not set in .env. Run scripts/install.sh first." >&2
  exit 1
fi

# ATLAS_DATABASE_URL is never written into .env itself -- install.sh/start.sh build it from
# ATLAS_POSTGRES_HOST/_PORT/_PASSWORD and set it only in the backend process's own environment.
# This script is a separate, short-lived process, so it must build the same URL itself here.
export ATLAS_DATABASE_URL="postgresql+psycopg://atlas:${ATLAS_POSTGRES_PASSWORD}@${ATLAS_POSTGRES_HOST}:${ATLAS_POSTGRES_PORT}/atlas"

cd "$REPO_ROOT/backend"
uv run python scripts/bootstrap_admin.py
