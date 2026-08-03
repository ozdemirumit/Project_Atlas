[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $RepositoryRoot "backend")
try {
    uv run ruff format --check .
    uv run ruff check .
    uv run mypy
    uv run pytest
}
finally {
    Pop-Location
}

Push-Location (Join-Path $RepositoryRoot "frontend")
try {
    pnpm lint
    pnpm typecheck
    pnpm test
    pnpm build
}
finally {
    Pop-Location
}

Write-Host "All available Atlas checks passed."
