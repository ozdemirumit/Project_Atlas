# Stops the backend process scripts/start.ps1 (or scripts/install.ps1) started, without touching
# the database or any installed dependency.
#
# Usage:
#   ./scripts/stop.ps1

[CmdletBinding()]
param()

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $RepositoryRoot ".atlas"
$BackendPidFile = Join-Path $RuntimeDir "backend.pid"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message"
}

if (-not (Test-Path $BackendPidFile)) {
    Write-Step "Atlas backend is not running (no $BackendPidFile)."
    exit 0
}

$processId = Get-Content $BackendPidFile
if ($processId -and (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
    Write-Step "Stopping backend (pid $processId)."
    & taskkill /PID $processId /T /F *>$null
}
else {
    Write-Step "Atlas backend is not running (stale pid file)."
}
Remove-Item $BackendPidFile -Force -ErrorAction SilentlyContinue

Write-Step "Project Atlas stopped. Database data was kept; start it again with ./scripts/start.ps1."
