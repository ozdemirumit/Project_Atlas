[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepositoryRoot "backend"
$FrontendRoot = Join-Path $RepositoryRoot "frontend"
$env:ATLAS_DEVELOPMENT_IDENTITY_ENABLED = "true"

$backend = Start-Process -FilePath "uv" -ArgumentList @(
    "run", "uvicorn", "atlas.main:app", "--app-dir", "src", "--host", "127.0.0.1", "--port", "8000", "--reload"
) -WorkingDirectory $BackendRoot -PassThru -NoNewWindow

$frontend = Start-Process -FilePath "pnpm" -ArgumentList @("dev") -WorkingDirectory $FrontendRoot -PassThru -NoNewWindow

Write-Host "Atlas API: http://localhost:8000"
Write-Host "Atlas web: http://localhost:5173"
Write-Host "Press Ctrl+C to stop both processes."

try {
    Wait-Process -Id $backend.Id, $frontend.Id
}
finally {
    foreach ($process in @($backend, $frontend)) {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
    }
}
