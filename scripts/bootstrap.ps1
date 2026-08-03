[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot

function Require-Command {
    param([Parameter(Mandatory)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not available. See README.md for prerequisites."
    }
}

Require-Command "uv"
Require-Command "pnpm"

Write-Host "Preparing Atlas backend..."
Push-Location (Join-Path $RepositoryRoot "backend")
try {
    uv sync --frozen
}
finally {
    Pop-Location
}

Write-Host "Preparing Atlas web application..."
Push-Location (Join-Path $RepositoryRoot "frontend")
try {
    pnpm install --frozen-lockfile
}
finally {
    Pop-Location
}

Write-Host "Atlas development dependencies are ready."
