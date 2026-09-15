# Stops the backend/frontend processes scripts/install.ps1 started.
#
# Usage:
#   ./scripts/uninstall.ps1          # stop backend + frontend, keep the database
#   ./scripts/uninstall.ps1 -Purge   # also drop the atlas database and role (destroys all data)

[CmdletBinding()]
param(
    [switch]$Purge
)

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $RepositoryRoot ".env"
$RuntimeDir = Join-Path $RepositoryRoot ".atlas"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message"
}

function Stop-IfRunning {
    param([string]$Name, [string]$PidFile)
    if (-not (Test-Path $PidFile)) { return }
    $processId = Get-Content $PidFile
    if ($processId) {
        Write-Step "Stopping $Name (pid $processId)."
        & taskkill /PID $processId /T /F *>$null
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

Stop-IfRunning "frontend" (Join-Path $RuntimeDir "frontend.pid")
Stop-IfRunning "backend" (Join-Path $RuntimeDir "backend.pid")

if ($Purge) {
    if (-not (Test-Path $EnvFile)) {
        Write-Step "No .env found; nothing to purge."
        exit 0
    }

    $envValues = @{}
    foreach ($line in Get-Content $EnvFile) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -eq 2) { $envValues[$parts[0].Trim()] = $parts[1].Trim() }
    }
    $postgresHost = $envValues["ATLAS_POSTGRES_HOST"]
    $postgresPort = $envValues["ATLAS_POSTGRES_PORT"]
    if ([string]::IsNullOrEmpty($postgresHost)) { $postgresHost = "localhost" }
    if ([string]::IsNullOrEmpty($postgresPort)) { $postgresPort = "5432" }

    Write-Step "Purging the atlas database and role (all data will be lost)."
    $suUser = Read-Host "PostgreSQL superuser name [postgres]"
    if ([string]::IsNullOrEmpty($suUser)) { $suUser = "postgres" }
    $suSecure = Read-Host "PostgreSQL superuser password" -AsSecureString
    $suBstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($suSecure)
    $suPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($suBstr)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($suBstr)

    $env:PGPASSWORD = $suPassword
    try {
        $dropDbArgs = @("-h", $postgresHost, "-p", $postgresPort, "-U", $suUser, "-d", "postgres",
            "-v", "ON_ERROR_STOP=1", "-c", "DROP DATABASE IF EXISTS atlas")
        & psql @dropDbArgs

        $dropRoleArgs = @("-h", $postgresHost, "-p", $postgresPort, "-U", $suUser, "-d", "postgres",
            "-v", "ON_ERROR_STOP=1", "-c", "DROP ROLE IF EXISTS atlas")
        & psql @dropRoleArgs
    }
    finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
        $suPassword = $null
    }
}
else {
    Write-Step "Database was kept. Re-run ./scripts/install.ps1 to start again with the same data, or pass -Purge to delete it."
}

Write-Step "Project Atlas stopped."
