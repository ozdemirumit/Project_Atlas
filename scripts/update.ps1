# Updates an already-installed Project Atlas deployment to the latest commit: stops the backend,
# pulls the latest code, then re-runs install.ps1 (not just start.ps1) so any new backend
# dependency or database migration the pull brought in is actually applied before the backend
# starts again -- restarting with `start.ps1` alone after a pull that added a dependency or
# migration would silently run stale code against an unmigrated schema.
#
# Usage:
#   ./scripts/update.ps1
#
# Refuses to run with uncommitted local changes in the repository, so it never discards work by
# pulling over it. Commit or stash first if this refuses to run.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message"
}

function Invoke-NativeAllowFailure {
    # Windows PowerShell 5.1 wraps a native command's stderr text into a terminating error when it
    # also exits non-zero and $ErrorActionPreference = "Stop" is in effect -- regardless of stream
    # redirection. git itself can also write informational text to stderr on a *successful* run
    # (e.g. progress output), which would otherwise abort this script on a false positive. Every
    # git call here goes through this, matching install.ps1's own established fix for the same
    # issue.
    param([Parameter(Mandatory)][scriptblock]$ScriptBlock)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $ScriptBlock
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

Push-Location $RepositoryRoot
try {
    if (-not (Test-Path (Join-Path $RepositoryRoot ".git"))) {
        throw "$RepositoryRoot is not a git repository; cannot update."
    }

    $dirty = Invoke-NativeAllowFailure { git status --porcelain }
    if ($LASTEXITCODE -ne 0) {
        throw "git status failed; see output above."
    }
    if ($dirty) {
        throw "There are uncommitted local changes. Commit or stash them first, then re-run " +
            "./scripts/update.ps1 -- this script refuses to pull over uncommitted work."
    }

    Write-Step "Stopping the backend."
    & (Join-Path $PSScriptRoot "stop.ps1")

    Write-Step "Pulling the latest code."
    Invoke-NativeAllowFailure { git pull --ff-only }
    if ($LASTEXITCODE -ne 0) {
        throw "git pull --ff-only failed. If your local branch has diverged from its remote " +
            "tracking branch, resolve that manually (e.g. git pull --rebase, or git merge), then " +
            "re-run ./scripts/update.ps1."
    }

    Write-Step "Reinstalling dependencies, applying migrations, and starting the backend."
    & (Join-Path $PSScriptRoot "install.ps1")
}
finally {
    Pop-Location
}
