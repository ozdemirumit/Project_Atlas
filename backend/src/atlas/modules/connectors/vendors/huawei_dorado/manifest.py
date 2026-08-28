from __future__ import annotations

from urllib.parse import urlsplit

from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    ConnectorPackageManifest,
    IdempotencyClass,
    SideEffect,
)

SYSTEM_IDENTITY_CAPABILITY_ID = "huawei.dorado.storage.system.read"
CONTROLLER_HEALTH_CAPABILITY_ID = "huawei.dorado.storage.controller.read"
CAPACITY_CAPABILITY_ID = "huawei.dorado.storage.pool.read"
# Aspirational, mirroring hitachi_ops_center/manifest.py's PATH_EVENTS_CAPABILITY_ID: referenced
# by RCA diagnostic-step descriptions as a capability a human operator could run against this
# vendor; not yet implemented by HuaweiDoradoClient and therefore not declared in
# build_candidate_manifest()'s capabilities tuple below.
PATH_EVENTS_CAPABILITY_ID = "huawei.dorado.storage.path-events.read"
# Aspirational, mirroring hitachi_ops_center/manifest.py's CONTROLLER_FAILOVER_PLAN_CAPABILITY_ID
# and PATH_REMEDIATION_PLAN_CAPABILITY_ID: referenced by recommendation plan-step descriptions as
# capabilities a human operator could run against this vendor; not yet implemented and not
# declared in build_candidate_manifest()'s capabilities tuple below.
CONTROLLER_FAILOVER_PLAN_CAPABILITY_ID = "huawei.dorado.storage.controller-failover.plan"
PATH_REMEDIATION_PLAN_CAPABILITY_ID = "huawei.dorado.storage.path-remediation.plan"
PACKAGE_ID = "connector.huawei.dorado.device-manager"
OFFICIAL_REFERENCE = "https://support.huawei.com/enterprise/en/doc/EDOC1100144155"


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
        display_name="Huawei OceanStor Dorado DeviceManager",
        publisher="Project Atlas",
        owner="Storage Platform Engineering",
        package_version="0.1.0",
        atlas_compatibility=">=0.1.0,<0.2.0",
        runtime="python.http",
        entry_point="atlas.modules.connectors.vendors.huawei_dorado.client:HuaweiDoradoClient",
        digest_sha256=digest_sha256,
        supported_products=(
            "OceanStor Dorado 6.1.0 series",
            "OceanStor Dorado 3000/5000/6000/8000/18000 V6",
        ),
        network_destinations=(network_destination,),
        capabilities=(
            CapabilityManifest(
                capability_id=SYSTEM_IDENTITY_CAPABILITY_ID,
                version="1.0.0",
                description="Read the identity and health of one exact Dorado system.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.storage.array",),
                timeout_seconds=30,
                idempotency=IdempotencyClass.SAFE,
            ),
            CapabilityManifest(
                capability_id=CONTROLLER_HEALTH_CAPABILITY_ID,
                version="1.0.0",
                description="Read bounded controller health for one exact Dorado system.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.storage.array",),
                timeout_seconds=60,
                idempotency=IdempotencyClass.SAFE,
            ),
            CapabilityManifest(
                capability_id=CAPACITY_CAPABILITY_ID,
                version="1.0.0",
                description="Read bounded storage pool capacity for one exact Dorado system.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.storage.array",),
                timeout_seconds=60,
                idempotency=IdempotencyClass.SAFE,
            ),
        ),
        generated=True,
    )
