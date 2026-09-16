[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $RepositoryRoot ".env"

if (-not (Test-Path $EnvFile)) {
    throw "No .env found. Run ./scripts/install.ps1 first."
}

$envValues = @{}
foreach ($line in Get-Content $EnvFile) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
    $parts = $trimmed -split "=", 2
    if ($parts.Count -eq 2) {
        $value = $parts[1].Trim()
        if ($value.StartsWith("'") -and $value.EndsWith("'") -and $value.Length -ge 2) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $envValues[$parts[0].Trim()] = $value
    }
}

$postgresPassword = $envValues["ATLAS_POSTGRES_PASSWORD"]
$postgresHost = $envValues["ATLAS_POSTGRES_HOST"]
$postgresPort = $envValues["ATLAS_POSTGRES_PORT"]
if ([string]::IsNullOrEmpty($postgresHost)) { $postgresHost = "localhost" }
if ([string]::IsNullOrEmpty($postgresPort)) { $postgresPort = "5432" }
if ([string]::IsNullOrEmpty($postgresPassword)) {
    throw "ATLAS_POSTGRES_PASSWORD is not set in .env. Run ./scripts/install.ps1 first."
}

# ATLAS_DATABASE_URL is never written into .env itself -- install.ps1/start.ps1 build it from
# ATLAS_POSTGRES_HOST/_PORT/_PASSWORD and set it only in the backend process's own environment.
# This script is a separate, short-lived process, so it must build the same URL itself here.
$env:ATLAS_DATABASE_URL = "postgresql+psycopg://atlas:${postgresPassword}@${postgresHost}:${postgresPort}/atlas"

Push-Location (Join-Path $RepositoryRoot "backend")
try {
    uv run python scripts/bootstrap_admin.py
    if ($LASTEXITCODE -ne 0) { throw "Administrator bootstrap failed." }
}
finally {
    Pop-Location
    Remove-Item Env:\ATLAS_DATABASE_URL -ErrorAction SilentlyContinue
}
