# Builds and starts Project Atlas (backend, frontend) as plain background processes against a
# PostgreSQL server you install yourself. No Docker, no containers, no YAML.
#
# Usage:
#   ./scripts/install.ps1
#
# Prerequisites: PostgreSQL (with the pgvector extension available), uv, pnpm. See README.md.
# Idempotent: re-running rebuilds dependencies and restarts the backend/frontend processes
# without touching existing database data. Run scripts/uninstall.ps1 to stop everything.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $RepositoryRoot ".env"
$EnvExample = Join-Path $RepositoryRoot ".env.example"
$RuntimeDir = Join-Path $RepositoryRoot ".atlas"

$BackendPort = 8000
$FrontendPort = 5173

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message"
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not available. See README.md for prerequisites."
    }
}

Require-Command "uv"
Require-Command "pnpm"
Require-Command "psql"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

# --- .env: create it from .env.example with a freshly generated database password ---

if (-not (Test-Path $EnvFile)) {
    Write-Step "No .env found; creating one from .env.example with a generated database password."
    if (-not (Test-Path $EnvExample)) {
        throw ".env.example is missing; cannot generate .env."
    }
    $bytes = New-Object byte[] 32
    $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    $generatedPassword = -join ($bytes | ForEach-Object { $_.ToString("x2") })
    (Get-Content $EnvExample) -replace '^ATLAS_POSTGRES_PASSWORD=.*', "ATLAS_POSTGRES_PASSWORD=$generatedPassword" |
        Set-Content -Path $EnvFile -Encoding utf8
    Write-Step "Created .env with a generated ATLAS_POSTGRES_PASSWORD. Keep this file private; it is already gitignored."
}
else {
    Write-Step "Using existing .env."
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
    throw "ATLAS_POSTGRES_PASSWORD is not set in .env."
}
if ($postgresPassword -eq "replace-with-a-local-development-secret") {
    throw "ATLAS_POSTGRES_PASSWORD in .env is still the placeholder value. Set a real secret and re-run."
}

# --- database: create the atlas role/database/extension only if they are not already usable ---

$env:PGPASSWORD = $postgresPassword
$checkArgs = @("-h", $postgresHost, "-p", $postgresPort, "-U", "atlas", "-d", "atlas", "-c", "SELECT 1")
& psql @checkArgs *>$null
$atlasReachable = ($LASTEXITCODE -eq 0)
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue

if ($atlasReachable) {
    Write-Step "Database already reachable as the atlas role; skipping superuser setup."
}
else {
    Write-Step "Database not reachable as the atlas role yet. One-time setup needs your PostgreSQL superuser credentials."
    $suUser = Read-Host "PostgreSQL superuser name [postgres]"
    if ([string]::IsNullOrEmpty($suUser)) { $suUser = "postgres" }
    $suSecure = Read-Host "PostgreSQL superuser password" -AsSecureString
    $suBstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($suSecure)
    $suPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($suBstr)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($suBstr)

    $env:PGPASSWORD = $suPassword
    try {
        $roleSql = @'
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'atlas') THEN
        EXECUTE format('CREATE ROLE atlas WITH LOGIN PASSWORD %L', :'pw');
    ELSE
        EXECUTE format('ALTER ROLE atlas WITH LOGIN PASSWORD %L', :'pw');
    END IF;
END
$$;
'@
        $roleArgs = @("-h", $postgresHost, "-p", $postgresPort, "-U", $suUser, "-d", "postgres",
            "-v", "ON_ERROR_STOP=1", "-v", "pw=$postgresPassword")
        $roleSql | & psql @roleArgs
        if ($LASTEXITCODE -ne 0) { throw "Failed to create/update the atlas role." }

        $dbCheckArgs = @("-h", $postgresHost, "-p", $postgresPort, "-U", $suUser, "-d", "postgres",
            "-tAc", "SELECT 1 FROM pg_database WHERE datname = 'atlas'")
        $dbExists = & psql @dbCheckArgs
        if ([string]::IsNullOrWhiteSpace($dbExists)) {
            Write-Step "Creating database 'atlas'."
            $createDbArgs = @("-h", $postgresHost, "-p", $postgresPort, "-U", $suUser, "-d", "postgres",
                "-v", "ON_ERROR_STOP=1", "-c", "CREATE DATABASE atlas OWNER atlas")
            & psql @createDbArgs
            if ($LASTEXITCODE -ne 0) { throw "Failed to create the atlas database." }
        }

        Write-Step "Enabling the pgvector extension (requires pgvector to already be installed on this PostgreSQL server)."
        $extensionArgs = @("-h", $postgresHost, "-p", $postgresPort, "-U", $suUser, "-d", "atlas",
            "-v", "ON_ERROR_STOP=1", "-c", "CREATE EXTENSION IF NOT EXISTS vector")
        & psql @extensionArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create the pgvector extension. Install pgvector on this PostgreSQL server first -- see README.md."
        }
    }
    finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
        $suPassword = $null
    }
}

$databaseUrl = "postgresql+psycopg://atlas:${postgresPassword}@${postgresHost}:${postgresPort}/atlas"

# --- backend: install dependencies and run migrations ---

Write-Step "Installing backend dependencies."
Push-Location (Join-Path $RepositoryRoot "backend")
try {
    uv sync --frozen
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed." }

    Write-Step "Running database migrations."
    $env:ATLAS_DATABASE_URL = $databaseUrl
    try {
        uv run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "alembic upgrade head failed." }
    }
    finally {
        Remove-Item Env:\ATLAS_DATABASE_URL -ErrorAction SilentlyContinue
    }
}
finally {
    Pop-Location
}

# --- frontend: install dependencies ---

Write-Step "Installing frontend dependencies."
Push-Location (Join-Path $RepositoryRoot "frontend")
try {
    pnpm install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw "pnpm install failed." }
}
finally {
    Pop-Location
}

# --- start backend + frontend as background processes ---

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

function Stop-IfRunning {
    param([string]$PidFile)
    if (-not (Test-Path $PidFile)) { return }
    $processId = Get-Content $PidFile
    if ($processId) {
        & taskkill /PID $processId /T /F *>$null
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

Write-Step "Starting the backend on port $BackendPort."
$backendPidFile = Join-Path $RuntimeDir "backend.pid"
Stop-IfRunning $backendPidFile
$backendEnv = @{
    ATLAS_ENVIRONMENT = "development"
    ATLAS_DATABASE_REQUIRED = "true"
    ATLAS_DATABASE_URL = $databaseUrl
    ATLAS_DEVELOPMENT_IDENTITY_ENABLED = "true"
}
foreach ($key in $backendEnv.Keys) { [System.Environment]::SetEnvironmentVariable($key, $backendEnv[$key], "Process") }
$backendProcess = Start-Process -FilePath "uv" -ArgumentList @(
    "run", "uvicorn", "atlas.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "$BackendPort"
) -WorkingDirectory (Join-Path $RepositoryRoot "backend") -PassThru -NoNewWindow `
    -RedirectStandardOutput (Join-Path $RuntimeDir "backend.log") `
    -RedirectStandardError (Join-Path $RuntimeDir "backend.error.log")
foreach ($key in $backendEnv.Keys) { [System.Environment]::SetEnvironmentVariable($key, $null, "Process") }
Set-Content -Path $backendPidFile -Value $backendProcess.Id

Write-Step "Waiting for the backend to become healthy."
if (-not (Wait-ForHttp "http://127.0.0.1:$BackendPort/health/ready" 30 2)) {
    throw "Backend did not become healthy in time. Check: $RuntimeDir\backend.log / backend.error.log"
}

Write-Step "Starting the frontend on port $FrontendPort."
$frontendPidFile = Join-Path $RuntimeDir "frontend.pid"
Stop-IfRunning $frontendPidFile
[System.Environment]::SetEnvironmentVariable("ATLAS_API_PROXY_TARGET", "http://127.0.0.1:$BackendPort", "Process")
$frontendProcess = Start-Process -FilePath "pnpm" -ArgumentList @(
    "dev", "--host", "0.0.0.0", "--port", "$FrontendPort"
) -WorkingDirectory (Join-Path $RepositoryRoot "frontend") -PassThru -NoNewWindow `
    -RedirectStandardOutput (Join-Path $RuntimeDir "frontend.log") `
    -RedirectStandardError (Join-Path $RuntimeDir "frontend.error.log")
[System.Environment]::SetEnvironmentVariable("ATLAS_API_PROXY_TARGET", $null, "Process")
Set-Content -Path $frontendPidFile -Value $frontendProcess.Id

Write-Step "Waiting for the frontend to become available."
if (-not (Wait-ForHttp "http://127.0.0.1:$FrontendPort/" 30 2)) {
    throw "Frontend did not become available in time. Check: $RuntimeDir\frontend.log / frontend.error.log"
}

Write-Host @"

Project Atlas is running.

  Web application: http://localhost:$FrontendPort
  API:              http://localhost:$BackendPort
  API docs:         http://localhost:$BackendPort/docs

Stop everything with: ./scripts/uninstall.ps1
View logs with: Get-Content -Wait $RuntimeDir\backend.log
"@
