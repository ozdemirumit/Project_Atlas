from __future__ import annotations

from urllib.parse import urlsplit

from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    ConnectorPackageManifest,
    IdempotencyClass,
    SideEffect,
)

INVENTORY_CAPABILITY_ID = "hitachi.opscenter.storage.inventory.read"
HEALTH_CAPABILITY_ID = "hitachi.opscenter.storage.health.read"
# Backed by HitachiOpsCenterClient.read_hardware_health() and referenced across RCA, health-check,
# and recommendation application services as the allowed "read hardware health" capability for
# this vendor. Named ".hardware.read", distinct from HEALTH_CAPABILITY_ID above (".health.read",
# used only by the bundled-catalog descriptor) -- a pre-existing naming inconsistency, not
# introduced or resolved here; both are exposed as constants so consumers stop retyping either
# literal string.
HARDWARE_HEALTH_CAPABILITY_ID = "hitachi.opscenter.storage.hardware.read"
# Referenced by RCA/health-check diagnostic-step descriptions as capabilities a human operator
# could run against this vendor; not yet implemented by HitachiOpsCenterClient and therefore not
# declared in build_candidate_manifest()'s capabilities tuple below. Kept here as named constants
# so consuming modules import a stable identifier instead of retyping the literal string.
CAPACITY_CAPABILITY_ID = "hitachi.opscenter.storage.capacity.read"
PATH_EVENTS_CAPABILITY_ID = "hitachi.opscenter.storage.path-events.read"
CONTROLLER_FAILOVER_PLAN_CAPABILITY_ID = "hitachi.opscenter.storage.controller-failover.plan"
PATH_REMEDIATION_PLAN_CAPABILITY_ID = "hitachi.opscenter.storage.path-remediation.plan"
PACKAGE_ID = "connector.hitachi.opscenter.configuration-manager"
OFFICIAL_REFERENCE = "https://docs.hitachivantara.com/r/en-us/mk-99cfm000/latest"


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
        display_name="Hitachi Ops Center API Configuration Manager",
        publisher="Project Atlas",
        owner="Storage Platform Engineering",
        package_version="0.1.0",
        atlas_compatibility=">=0.1.0,<0.2.0",
        runtime="python.http",
        entry_point=(
            "atlas.modules.connectors.vendors.hitachi_ops_center.client:HitachiOpsCenterClient"
        ),
        digest_sha256=digest_sha256,
        supported_products=(
            "Hitachi Ops Center API Configuration Manager 11.0.x",
            "VSP One B20 series",
            "VSP 5000 series",
            "VSP E series",
            "VSP Gx00 and Fx00 supported models",
        ),
        network_destinations=(network_destination,),
        capabilities=(
            CapabilityManifest(
                capability_id=INVENTORY_CAPABILITY_ID,
                version="1.0.0",
                description="Read the storage systems visible to Configuration Manager.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.storage.management",),
                timeout_seconds=30,
                idempotency=IdempotencyClass.SAFE,
            ),
            CapabilityManifest(
                capability_id=HEALTH_CAPABILITY_ID,
                version="1.0.0",
                description="Read bounded hardware health for one exact storage system.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.storage.array",),
                timeout_seconds=60,
                idempotency=IdempotencyClass.SAFE,
            ),
        ),
        generated=True,
    )
