from __future__ import annotations

from urllib.parse import urlsplit

from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    ConnectorPackageManifest,
    IdempotencyClass,
    SideEffect,
)

CLUSTER_NODE_CAPABILITY_ID = "huawei.pacific.storage.cluster.read"
STORAGE_POOL_CAPABILITY_ID = "huawei.pacific.storage.pool.read"
# Aspirational, mirroring huawei_dorado/manifest.py's PATH_EVENTS_CAPABILITY_ID and
# CONTROLLER_FAILOVER_PLAN_CAPABILITY_ID/PATH_REMEDIATION_PLAN_CAPABILITY_ID: referenced by RCA
# diagnostic-step and recommendation plan-step descriptions as capabilities a human operator
# could run against this vendor; not yet implemented by HuaweiPacificClient and therefore not
# declared in build_candidate_manifest()'s capabilities tuple below.
NODE_EVENTS_CAPABILITY_ID = "huawei.pacific.storage.node-events.read"
CLUSTER_FAILOVER_PLAN_CAPABILITY_ID = "huawei.pacific.storage.cluster-failover.plan"
NODE_REMEDIATION_PLAN_CAPABILITY_ID = "huawei.pacific.storage.node-remediation.plan"
PACKAGE_ID = "connector.huawei.pacific.cluster-manager"
OFFICIAL_REFERENCE = "https://support.huawei.com/enterprise/en/doc/EDOC1100194144"


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
        display_name="Huawei OceanStor Pacific Cluster Manager",
        publisher="Project Atlas",
        owner="Storage Platform Engineering",
        package_version="0.1.0",
        atlas_compatibility=">=0.1.0,<0.2.0",
        runtime="python.http",
        entry_point="atlas.modules.connectors.vendors.huawei_pacific.client:HuaweiPacificClient",
        digest_sha256=digest_sha256,
        supported_products=(
            "OceanStor Pacific 8.1.0 series",
            "OceanStor Pacific 9350/9550/9920 scale-out storage",
        ),
        network_destinations=(network_destination,),
        capabilities=(
            CapabilityManifest(
                capability_id=CLUSTER_NODE_CAPABILITY_ID,
                version="1.0.0",
                description="Read cluster node identity and running status for one exact cluster.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.storage.cluster",),
                timeout_seconds=30,
                idempotency=IdempotencyClass.SAFE,
            ),
            CapabilityManifest(
                capability_id=STORAGE_POOL_CAPABILITY_ID,
                version="1.0.0",
                description="Read bounded storage pool capacity for one exact cluster.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.storage.cluster",),
                timeout_seconds=60,
                idempotency=IdempotencyClass.SAFE,
            ),
        ),
        generated=True,
    )
