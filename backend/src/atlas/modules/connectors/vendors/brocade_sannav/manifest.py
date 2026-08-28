from __future__ import annotations

from urllib.parse import urlsplit

from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    ConnectorPackageManifest,
    IdempotencyClass,
    SideEffect,
)

FABRIC_INVENTORY_CAPABILITY_ID = "brocade.sannav.fabric.inventory.read"
FABRIC_HEALTH_CAPABILITY_ID = "brocade.sannav.fabric.health.read"
PACKAGE_ID = "connector.brocade.sannav.management-portal"
OFFICIAL_REFERENCE = (
    "https://techdocs.broadcom.com/us/en/fibre-channel-networking/sannav/"
    "management-portal-rest-api/3-0-0x/SANnav-Overview.html"
)


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
        display_name="Brocade SANnav Management Portal",
        publisher="Project Atlas",
        owner="Storage Platform Engineering",
        package_version="0.1.0",
        atlas_compatibility=">=0.1.0,<0.2.0",
        runtime="python.http",
        entry_point=("atlas.modules.connectors.vendors.brocade_sannav.client:BrocadeSanNavClient"),
        digest_sha256=digest_sha256,
        supported_products=(
            "Brocade SANnav Management Portal 2.3.x",
            "Brocade SANnav Management Portal 2.4.x",
            "Brocade SANnav Management Portal 3.0.x",
        ),
        network_destinations=(network_destination,),
        capabilities=(
            CapabilityManifest(
                capability_id=FABRIC_INVENTORY_CAPABILITY_ID,
                version="1.0.0",
                description="Read the fabrics and member switches visible to SANnav.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.san.fabric",),
                timeout_seconds=30,
                idempotency=IdempotencyClass.SAFE,
            ),
            CapabilityManifest(
                capability_id=FABRIC_HEALTH_CAPABILITY_ID,
                version="1.0.0",
                description=("Read a bounded count of recent fault events for one exact fabric."),
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.san.fabric",),
                timeout_seconds=60,
                idempotency=IdempotencyClass.SAFE,
            ),
        ),
        generated=True,
    )
