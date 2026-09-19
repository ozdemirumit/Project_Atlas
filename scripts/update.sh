#!/usr/bin/env bash
# Updates an already-installed Project Atlas deployment to the latest commit: stops the backend,
# pulls the latest code, then re-runs install.sh (not just start.sh) so any new backend
# dependency or database migration the pull brought in is actually applied before the backend
# starts again -- restarting with start.sh alone after a pull that added a dependency or
# migration would silently run stale code against an unmigrated schema.
#
# Usage:
#   scripts/update.sh
#
# Refuses to run with uncommitted local changes in the repository, so it never discards work by
# pulling over it. Commit or stash first if this refuses to run.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nError: %s\n' "$1" >&2; exit 1; }

cd "$REPO_ROOT"

[ -d "$REPO_ROOT/.git" ] || fail "$REPO_ROOT is not a git repository; cannot update."

if [ -n "$(git status --porcelain)" ]; then
    fail "There are uncommitted local changes. Commit or stash them first, then re-run scripts/update.sh -- this script refuses to pull over uncommitted work."
fi

log "Stopping the backend."
"$REPO_ROOT/scripts/stop.sh"

log "Pulling the latest code."
git pull --ff-only \
    || fail "git pull --ff-only failed. If your local branch has diverged from its remote tracking branch, resolve that manually (e.g. git pull --rebase, or git merge), then re-run scripts/update.sh."

log "Reinstalling dependencies, applying migrations, and starting the backend."
"$REPO_ROOT/scripts/install.sh"
