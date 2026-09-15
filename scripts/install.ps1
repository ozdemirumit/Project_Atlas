# Builds and starts Project Atlas (backend, frontend) as plain background processes. No Docker,
# no containers, no YAML.
#
# Usage:
#   ./scripts/install.ps1   (run as Administrator the first time, if pgvector needs building)
#
# uv, pnpm, and PostgreSQL (via winget) are installed automatically if missing, asking for
# confirmation first. pgvector has no Windows binary distribution, so it is built from source --
# this installs Visual Studio C++ Build Tools automatically if needed (several GB) and requires
# an elevated PowerShell session. See README.md.
#
# On a network that blocks direct downloads (e.g. a proxy that blocks .exe files by policy),
# obtain the files through an approved channel yourself and pass their local paths instead:
#   ./scripts/install.ps1 -VcBuildToolsInstaller C:\path\to\vs_buildtools.exe -PgVectorArchive C:\path\to\pgvector.zip
# Idempotent: re-running rebuilds dependencies and restarts the backend/frontend processes
# without touching existing database data. Run scripts/uninstall.ps1 to stop everything.

[CmdletBinding()]
param(
    # Local path to an already-downloaded vs_buildtools.exe (Visual Studio C++ Build Tools
    # bootstrapper, normally fetched from https://aka.ms/vs/17/release/vs_buildtools.exe).
    # Use this when your network blocks that download.
    [string]$VcBuildToolsInstaller = "",
    # Local path to an already-downloaded pgvector source archive (normally fetched from
    # https://github.com/pgvector/pgvector/archive/refs/tags/v0.8.6.zip). Use this when your
    # network blocks that download.
    [string]$PgVectorArchive = ""
)

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

function Update-SessionPath {
    # Machine/User PATH entries can be REG_EXPAND_SZ values containing unexpanded %VAR%
    # references (pnpm's installer, for one, writes "%PNPM_HOME%\bin" rather than a literal
    # path) -- GetEnvironmentVariable returns them raw. Import every Machine/User variable into
    # this process first so those references resolve, then expand PATH against them explicitly.
    foreach ($scope in @("Machine", "User")) {
        foreach ($entry in [Environment]::GetEnvironmentVariables($scope).GetEnumerator()) {
            if ($entry.Key -ne "Path") {
                [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
            }
        }
    }
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = [Environment]::ExpandEnvironmentVariables("$machinePath;$userPath")
}

function Ensure-Uv {
    if (Get-Command uv -ErrorAction SilentlyContinue) { return }
    Write-Step "uv not found; installing it with the official installer (user-local, no admin required)."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    Update-SessionPath
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv installation failed. Install it manually: https://docs.astral.sh/uv/getting-started/installation/"
    }
}

function Ensure-Pnpm {
    if (Get-Command pnpm -ErrorAction SilentlyContinue) { return }
    Write-Step "pnpm not found; installing it with the official installer (user-local, no admin required)."
    Invoke-RestMethod https://get.pnpm.io/install.ps1 | Invoke-Expression
    Update-SessionPath
    if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
        throw "pnpm installation failed. Install it manually: https://pnpm.io/installation"
    }
}

function Ensure-PostgreSql {
    if (Get-Command psql -ErrorAction SilentlyContinue) { return }
    Write-Step "PostgreSQL (psql) not found."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Could not find winget to auto-install PostgreSQL. Install PostgreSQL (with pgvector) yourself -- see README.md -- then re-run."
    }
    $confirm = Read-Host "Launch the PostgreSQL 18 installer with winget now? You will still need to complete its setup wizard (superuser password, port) [y/N]"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        throw "PostgreSQL is required. Install it yourself -- see README.md -- then re-run."
    }
    winget install -e --id PostgreSQL.PostgreSQL --accept-package-agreements --accept-source-agreements
    Update-SessionPath
    if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
        throw "PostgreSQL installation finished but 'psql' is still not on PATH. Open a new PowerShell window and re-run."
    }
}

# pgvector ships no Windows binaries at all (confirmed against its GitHub releases and its own
# README) -- the only way to get it on Windows is a source build with the MSVC C++ toolchain.
# Both installing that toolchain and running `nmake ... install` need to write into
# "Program Files", so this whole step requires an elevated (Administrator) PowerShell session.
function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Import-VcVars {
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) { throw "vswhere.exe not found; the Build Tools installation may have failed." }
    $vsInstallPath = & $vswhere -latest -products * `
        -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ([string]::IsNullOrWhiteSpace($vsInstallPath)) {
        throw "Could not find a Visual Studio C++ toolchain installation via vswhere."
    }
    $vcvarsPath = Join-Path $vsInstallPath "VC\Auxiliary\Build\vcvarsall.bat"
    $output = cmd.exe /c "`"$vcvarsPath`" x64 && set"
    foreach ($line in $output) {
        if ($line -match "^([^=]+)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}

function Test-WindowsSdkAvailable {
    # The MSVC compiler needs the Universal CRT headers (corecrt.h and friends), which ship in
    # the Windows SDK -- a component separate from the compiler itself. Checking for the actual
    # header, rather than a specific versioned SDK component ID, avoids depending on exactly
    # which SDK version happens to be current in the VS Build Tools channel manifest.
    $sdkIncludeRoot = "${env:ProgramFiles(x86)}\Windows Kits\10\Include"
    if (-not (Test-Path $sdkIncludeRoot)) { return $false }
    return $null -ne (Get-ChildItem -Path $sdkIncludeRoot -Filter "corecrt.h" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Ensure-VcBuildTools {
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    $hasVcTools = $false
    if (Test-Path $vswhere) {
        $existing = & $vswhere -latest -products * `
            -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        $hasVcTools = -not [string]::IsNullOrWhiteSpace($existing)
    }
    if ($hasVcTools -and (Test-WindowsSdkAvailable)) { return }

    Write-Step "Visual Studio C++ Build Tools and/or the Windows SDK are missing; installing/repairing them (this can download several GB and take a while)."
    $ownDownload = $false
    if ($VcBuildToolsInstaller -ne "") {
        if (-not (Test-Path $VcBuildToolsInstaller)) { throw "-VcBuildToolsInstaller path not found: $VcBuildToolsInstaller" }
        $installer = $VcBuildToolsInstaller
    }
    else {
        $installer = Join-Path $env:TEMP "vs_buildtools.exe"
        $ownDownload = $true
        try {
            Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vs_buildtools.exe" -OutFile $installer
        }
        catch {
            throw "Could not download the Visual Studio Build Tools installer -- your network may block it (e.g. " +
                "a proxy blocking .exe downloads). Ask your network/IT team to allow " +
                "https://aka.ms/vs/17/release/vs_buildtools.exe, or download it yourself through an approved " +
                "channel and re-run with -VcBuildToolsInstaller <path-to-vs_buildtools.exe>. Original error: $_"
        }
    }
    $process = Start-Process -FilePath $installer -ArgumentList @(
        "--quiet", "--wait", "--norestart", "--nocache",
        "--add", "Microsoft.VisualStudio.Workload.VCTools",
        "--add", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
        "--includeRecommended"
    ) -PassThru -Wait
    if ($ownDownload) { Remove-Item $installer -Force -ErrorAction SilentlyContinue }
    if ($process.ExitCode -ne 0 -and $process.ExitCode -ne 3010) {
        throw "Visual Studio Build Tools installation failed (exit code $($process.ExitCode))."
    }
    if (-not (Test-WindowsSdkAvailable)) {
        throw "Visual Studio Build Tools installed but the Windows SDK (corecrt.h) is still missing. " +
            "Open the Visual Studio Installer, Modify the Build Tools installation, and add a " +
            "'Windows 10/11 SDK' component under Individual components, then re-run."
    }
}

function Ensure-PgVector {
    $pgShareDir = (& pg_config --sharedir).Trim()
    if (Test-Path (Join-Path $pgShareDir "extension\vector.control")) { return }

    Write-Step "pgvector is not installed on this PostgreSQL server."
    if (-not (Test-IsAdministrator)) {
        throw "Building pgvector needs an elevated PowerShell session. Re-run this script as Administrator."
    }
    $confirm = Read-Host "Build and install pgvector from source now? Installs Visual Studio C++ Build Tools first if needed (several GB, several minutes) [y/N]"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        throw "pgvector is required. Build it yourself -- see README.md -- then re-run."
    }

    Ensure-VcBuildTools
    Import-VcVars

    $pgBinDir = (& pg_config --bindir).Trim()
    $env:PGROOT = Split-Path -Parent $pgBinDir

    $buildDir = Join-Path $env:TEMP "pgvector-build"
    Remove-Item -Recurse -Force $buildDir -ErrorAction SilentlyContinue
    $ownZipDownload = $false
    if ($PgVectorArchive -ne "") {
        if (-not (Test-Path $PgVectorArchive)) { throw "-PgVectorArchive path not found: $PgVectorArchive" }
        $zipPath = $PgVectorArchive
    }
    else {
        $zipPath = Join-Path $env:TEMP "pgvector.zip"
        $ownZipDownload = $true
        try {
            Invoke-WebRequest -Uri "https://github.com/pgvector/pgvector/archive/refs/tags/v0.8.6.zip" -OutFile $zipPath
        }
        catch {
            throw ("Could not download pgvector -- your network may block it. Ask your network/IT team to allow " +
                "github.com, or download " +
                "https://github.com/pgvector/pgvector/archive/refs/tags/v0.8.6.zip yourself through an approved " +
                "channel and re-run with -PgVectorArchive <path-to-pgvector.zip>. Original error: $_")
        }
    }
    Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
    if ($ownZipDownload) { Remove-Item $zipPath -Force }
    Rename-Item (Join-Path $env:TEMP "pgvector-0.8.6") $buildDir

    Push-Location $buildDir
    try {
        & nmake /F Makefile.win
        if ($LASTEXITCODE -ne 0) { throw "pgvector build failed (nmake exit code $LASTEXITCODE)." }
        & nmake /F Makefile.win install
        if ($LASTEXITCODE -ne 0) { throw "pgvector install failed (nmake exit code $LASTEXITCODE)." }
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path (Join-Path $pgShareDir "extension\vector.control"))) {
        throw "pgvector build finished but vector.control is still missing from $pgShareDir\extension."
    }
}

Ensure-Uv
Ensure-Pnpm
Ensure-PostgreSql
Ensure-PgVector

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
