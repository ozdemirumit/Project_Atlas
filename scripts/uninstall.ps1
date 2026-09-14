# Stops and removes the containers and network scripts/install.ps1 created.
#
# Usage:
#   ./scripts/uninstall.ps1          # stop and remove containers + network, keep the database volume
#   ./scripts/uninstall.ps1 -Purge   # also delete the database volume (destroys all data)

[CmdletBinding()]
param(
    [switch]$Purge
)

$NetworkName = "atlas-network"
$VolumeName = "atlas-postgres-data"
$Containers = @("atlas-frontend", "atlas-backend", "atlas-database")

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message"
}

foreach ($container in $Containers) {
    docker inspect $container *>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Step "Removing container $container."
        docker rm -f $container | Out-Null
    }
}

docker network inspect $NetworkName *>$null
if ($LASTEXITCODE -eq 0) {
    Write-Step "Removing network $NetworkName."
    docker network rm $NetworkName | Out-Null
}

if ($Purge) {
    docker volume inspect $VolumeName *>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Step "Deleting volume $VolumeName (all database data will be lost)."
        docker volume rm $VolumeName | Out-Null
    }
}
else {
    Write-Step "Database volume '$VolumeName' was kept. Re-run ./scripts/install.ps1 to start again with the same data, or pass -Purge to delete it."
}

Write-Step "Project Atlas containers stopped and removed."
