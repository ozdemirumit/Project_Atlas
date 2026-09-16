#!/usr/bin/env bash
# Creates the first durable local administrator account (ATLAS-030 SS11 bootstrap). Run once, on
# the server, by someone with shell access -- see backend/scripts/bootstrap_admin.py for why that
# is the whole authorization model (no HTTP endpoint exists for this on purpose).
#
# Usage:
#   scripts/bootstrap_admin.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "Required command \"uv\" is not available. See README.md for prerequisites." >&2
  exit 1
fi

cd "$REPO_ROOT/backend"
uv run python scripts/bootstrap_admin.py
