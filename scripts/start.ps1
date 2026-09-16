# Starts the already-installed Atlas backend as a background process, without redoing
# dependency installation, PostgreSQL/pgvector setup, or database migrations -- for routine
# day-to-day process control (e.g. after a server reboot). Run scripts/install.ps1 first (and
# again after any code or dependency update); this script only starts what install already set up.
#
# Usage:
#   ./scripts/start.ps1
#
# Idempotent: if the backend is already running, this prints its status and does nothing.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $RepositoryRoot ".env"
$RuntimeDir = Join-Path $RepositoryRoot ".atlas"
$FrontendDist = Join-Path $RepositoryRoot "frontend\dist"
$BackendPidFile = Join-Path $RuntimeDir "backend.pid"

$BackendPort = 8000

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message"
}

function Test-ProcessRunning {
    param([int]$ProcessId)
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Wait-ForHttp {
    param([string]$Url, [int]$Attempts = 30, [int]$DelaySeconds = 2)
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 | Out-Null
            return $true
        }
        catch {
            Start-Sleep -Seconds $DelaySeconds
        }
    }
    return $false
}

if (-not (Test-Path $EnvFile)) {
    throw "No .env found. Run ./scripts/install.ps1 first -- it creates .env and completes the one-time PostgreSQL/dependency setup this script assumes is already done."
}
if (-not (Test-Path (Join-Path $FrontendDist "index.html"))) {
    throw "frontend/dist/ is missing or incomplete. Run ./scripts/install.ps1, which checks for this."
}

if (Test-Path $BackendPidFile) {
    $existingPid = Get-Content $BackendPidFile
    if ($existingPid -and (Test-ProcessRunning $existingPid)) {
        Write-Host "Atlas backend is already running (pid $existingPid) at http://localhost:$BackendPort"
        exit 0
    }
    Remove-Item $BackendPidFile -Force -ErrorAction SilentlyContinue
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
$databaseUrl = "postgresql+psycopg://atlas:${postgresPassword}@${postgresHost}:${postgresPort}/atlas"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

Write-Step "Starting the backend on port $BackendPort."
$backendEnv = @{
    ATLAS_ENVIRONMENT = "development"
    ATLAS_DATABASE_REQUIRED = "true"
    ATLAS_DATABASE_URL = $databaseUrl
    ATLAS_DEVELOPMENT_IDENTITY_ENABLED = "true"
}
foreach ($key in $backendEnv.Keys) { [System.Environment]::SetEnvironmentVariable($key, $backendEnv[$key], "Process") }
$backendProcess = Start-Process -FilePath "uv" -ArgumentList @(
    # See install.ps1 for why --loop asyncio:SelectorEventLoop is required on Windows.
    "run", "uvicorn", "atlas.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "$BackendPort",
    "--loop", "asyncio:SelectorEventLoop"
) -WorkingDirectory (Join-Path $RepositoryRoot "backend") -PassThru -NoNewWindow `
    -RedirectStandardOutput (Join-Path $RuntimeDir "backend.log") `
    -RedirectStandardError (Join-Path $RuntimeDir "backend.error.log")
foreach ($key in $backendEnv.Keys) { [System.Environment]::SetEnvironmentVariable($key, $null, "Process") }
Set-Content -Path $BackendPidFile -Value $backendProcess.Id

Write-Step "Waiting for the backend to become healthy."
if (-not (Wait-ForHttp "http://127.0.0.1:$BackendPort/health/ready" 30 2)) {
    throw "Backend did not become healthy in time. Check: $RuntimeDir\backend.log / backend.error.log"
}

Write-Host @"

Project Atlas is running.

  Web application: http://localhost:$BackendPort
  API docs:         http://localhost:$BackendPort/docs

Stop it with: ./scripts/stop.ps1
View logs with: Get-Content -Wait $RuntimeDir\backend.log
"@
