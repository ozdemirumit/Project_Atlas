# Builds and starts Project Atlas (database, backend, frontend) as plain Docker containers.
# No Docker Compose, no YAML -- everything here is imperative `docker build`/`docker run`.
#
# Usage:
#   ./scripts/install.ps1
#
# Idempotent: re-running rebuilds the images and replaces any existing Atlas containers.
# Run scripts/uninstall.ps1 to stop and remove everything this script creates.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $RepositoryRoot ".env"
$EnvExample = Join-Path $RepositoryRoot ".env.example"

$NetworkName = "atlas-network"
$VolumeName = "atlas-postgres-data"
$DatabaseContainer = "atlas-database"
$BackendContainer = "atlas-backend"
$FrontendContainer = "atlas-frontend"
$DatabaseImage = "pgvector/pgvector:pg18"
$BackendImage = "atlas-backend:local"
$FrontendImage = "atlas-frontend:local"

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

Require-Command "docker"
docker info *>$null
if ($LASTEXITCODE -ne 0) {
    throw "Docker does not appear to be running. Start Docker and try again."
}

# --- .env: create it from .env.example with a freshly generated database password ---

if (-not (Test-Path $EnvFile)) {
    Write-Step "No .env found; creating one from .env.example with a generated database password."
    if (-not (Test-Path $EnvExample)) {
        throw ".env.example is missing; cannot generate .env."
    }
    # RNGCryptoServiceProvider (rather than the newer RandomNumberGenerator.Fill) is used
    # because it is available on both Windows PowerShell 5.1 (.NET Framework) and PowerShell 7+.
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
if ([string]::IsNullOrEmpty($postgresPassword)) {
    throw "ATLAS_POSTGRES_PASSWORD is not set in .env."
}
if ($postgresPassword -eq "replace-with-a-local-development-secret") {
    throw "ATLAS_POSTGRES_PASSWORD in .env is still the placeholder value. Set a real secret and re-run."
}

# --- network + volume (idempotent) ---

docker network inspect $NetworkName *>$null
if ($LASTEXITCODE -ne 0) {
    Write-Step "Creating Docker network '$NetworkName'."
    docker network create $NetworkName | Out-Null
}

docker volume inspect $VolumeName *>$null
if ($LASTEXITCODE -ne 0) {
    Write-Step "Creating Docker volume '$VolumeName'."
    docker volume create $VolumeName | Out-Null
}

function Remove-IfExists {
    param([string]$Container)
    docker rm -f $Container *>$null
}

function Wait-Healthy {
    param([string]$Container, [int]$Attempts = 30, [int]$DelaySeconds = 2)
    for ($i = 0; $i -lt $Attempts; $i++) {
        $status = (docker inspect --format '{{.State.Health.Status}}' $Container 2>$null)
        if ($status -eq "healthy") { return }
        if ($status -eq "unhealthy") {
            throw "$Container reported unhealthy. Check: docker logs $Container"
        }
        Start-Sleep -Seconds $DelaySeconds
    }
    throw "$Container did not become healthy in time. Check: docker logs $Container"
}

# Native docker.exe arguments are passed as an array and invoked with `&` throughout this
# script (rather than one long backtick-continued line) -- PowerShell's argument marshalling
# for native commands is unreliable once a single argument contains both spaces and quotes,
# which the health-check commands below do.

# --- database ---

Write-Step "Starting PostgreSQL ($DatabaseContainer)."
Remove-IfExists $DatabaseContainer
$databaseArgs = @(
    "run", "-d",
    "--name", $DatabaseContainer,
    "--network", $NetworkName,
    "--restart", "unless-stopped",
    "-e", "POSTGRES_DB=atlas",
    "-e", "POSTGRES_USER=atlas",
    "-e", "POSTGRES_PASSWORD=$postgresPassword",
    "-v", "${VolumeName}:/var/lib/postgresql/data",
    "--health-cmd", "pg_isready -U atlas -d atlas",
    "--health-interval", "5s",
    "--health-timeout", "3s",
    "--health-retries", "10",
    "--health-start-period", "10s",
    $DatabaseImage
)
& docker @databaseArgs | Out-Null

Write-Step "Waiting for PostgreSQL to become healthy."
Wait-Healthy $DatabaseContainer 30 2

# --- backend ---

Write-Step "Building the backend image."
& docker build -t $BackendImage (Join-Path $RepositoryRoot "backend")

Write-Step "Starting the backend ($BackendContainer)."
Remove-IfExists $BackendContainer
$databaseUrl = "postgresql+psycopg://atlas:${postgresPassword}@${DatabaseContainer}:5432/atlas"
$backendHealthCmd = "python -c `"import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=2)`""
$backendArgs = @(
    "run", "-d",
    "--name", $BackendContainer,
    "--network", $NetworkName,
    "--restart", "unless-stopped",
    "-e", "ATLAS_ENVIRONMENT=development",
    "-e", "ATLAS_DATABASE_REQUIRED=true",
    "-e", "ATLAS_DATABASE_URL=$databaseUrl",
    "-e", "ATLAS_DEVELOPMENT_IDENTITY_ENABLED=true",
    "-p", "127.0.0.1:8000:8000",
    "--health-cmd", $backendHealthCmd,
    "--health-interval", "10s",
    "--health-timeout", "3s",
    "--health-retries", "6",
    "--health-start-period", "15s",
    "--entrypoint", "sh",
    $BackendImage,
    "-c", "uv run --no-dev alembic upgrade head && uv run --no-dev uvicorn atlas.main:app --app-dir src --host 0.0.0.0 --port 8000"
)
& docker @backendArgs | Out-Null

Write-Step "Waiting for the backend to become healthy (this runs the database migrations)."
Wait-Healthy $BackendContainer 30 3

# --- frontend ---

Write-Step "Building the frontend image."
& docker build -t $FrontendImage (Join-Path $RepositoryRoot "frontend")

Write-Step "Starting the frontend ($FrontendContainer)."
Remove-IfExists $FrontendContainer
$frontendArgs = @(
    "run", "-d",
    "--name", $FrontendContainer,
    "--network", $NetworkName,
    "--restart", "unless-stopped",
    "-p", "127.0.0.1:5173:8080",
    $FrontendImage
)
& docker @frontendArgs | Out-Null

Write-Step "Waiting for the frontend to become healthy."
Wait-Healthy $FrontendContainer 15 2

Write-Host @"

Project Atlas is running.

  Web application: http://localhost:5173
  API:              http://localhost:8000
  API docs:         http://localhost:8000/docs

Stop and remove everything with: ./scripts/uninstall.ps1
View logs with: docker logs -f $BackendContainer
"@
