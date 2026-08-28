from __future__ import annotations

from urllib.parse import urlsplit

from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    ConnectorPackageManifest,
    IdempotencyClass,
    SideEffect,
)

JOB_STATUS_CAPABILITY_ID = "commvault.commserve.job.status.read"
PACKAGE_ID = "connector.commvault.commserve"
OFFICIAL_REFERENCE = "https://api.commvault.com/docs/latest/api/cv/JobOperations/get-list-of-jobs/"


def build_candidate_manifest(
    *, digest_sha256: str, network_destination: str
) -> ConnectorPackageManifest:
    destination = urlsplit(f"//{network_destination}")
    try:
        port = destination.port
    except ValueError as exc:
        raise ValueError("network_destination has an invalid port") from exc
    if (
        destination.hostname is None
        or port is None
        or destination.username is not None
        or destination.password is not None
        or destination.path
        or destination.query
        or destination.fragment
    ):
        raise ValueError("network_destination must contain only an approved host and port")
    return ConnectorPackageManifest(
        package_id=PACKAGE_ID,
        connector_id=PACKAGE_ID,
        display_name="Commvault CommServe (REST API)",
        publisher="Project Atlas",
        owner="Backup Platform Engineering",
        package_version="0.1.0",
        atlas_compatibility=">=0.1.0,<0.2.0",
        runtime="python.http",
        entry_point="atlas.modules.connectors.vendors.commvault.client:CommvaultClient",
        digest_sha256=digest_sha256,
        supported_products=(
            "Commvault Platform Release 11.3x (CommServe REST API)",
            "Commvault Cloud (CommServe REST API)",
        ),
        network_destinations=(network_destination,),
        capabilities=(
            CapabilityManifest(
                capability_id=JOB_STATUS_CAPABILITY_ID,
                version="1.0.0",
                description="Read bounded recent backup job status for one exact CommServe.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.backup.commserve",),
                timeout_seconds=60,
                idempotency=IdempotencyClass.SAFE,
            ),
        ),
        generated=True,
    )
