[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $RepositoryRoot "backend")
try {
    uv run python scripts/bootstrap_admin.py
    if ($LASTEXITCODE -ne 0) { throw "Administrator bootstrap failed." }
}
finally {
    Pop-Location
}
