from __future__ import annotations

from urllib.parse import urlsplit

from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    ConnectorPackageManifest,
    IdempotencyClass,
    SideEffect,
)

HOST_INVENTORY_CAPABILITY_ID = "vmware.vcenter.host.inventory.read"
CLUSTER_INVENTORY_CAPABILITY_ID = "vmware.vcenter.cluster.inventory.read"
VM_INVENTORY_CAPABILITY_ID = "vmware.vcenter.vm.inventory.read"
PACKAGE_ID = "connector.vmware.vcenter.automation-api"
OFFICIAL_REFERENCE = (
    "https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere-sdks-tools/8-0/"
    "vmware-vsphere-automation-rest-programming-guide-8-0.html"
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
        display_name="VMware vCenter Server (vSphere Automation API)",
        publisher="Project Atlas",
        owner="Virtualization Platform Engineering",
        package_version="0.1.0",
        atlas_compatibility=">=0.1.0,<0.2.0",
        runtime="python.http",
        entry_point="atlas.modules.connectors.vendors.vcenter.client:VCenterClient",
        digest_sha256=digest_sha256,
        supported_products=(
            "VMware vCenter Server 7.0 U2+",
            "VMware vCenter Server 8.0.x",
        ),
        network_destinations=(network_destination,),
        capabilities=(
            CapabilityManifest(
                capability_id=HOST_INVENTORY_CAPABILITY_ID,
                version="1.0.0",
                description="Read the ESXi hosts visible to this vCenter Server.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.hypervisor.vcenter",),
                timeout_seconds=30,
                idempotency=IdempotencyClass.SAFE,
            ),
            CapabilityManifest(
                capability_id=CLUSTER_INVENTORY_CAPABILITY_ID,
                version="1.0.0",
                description="Read the compute clusters visible to this vCenter Server.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.hypervisor.vcenter",),
                timeout_seconds=30,
                idempotency=IdempotencyClass.SAFE,
            ),
            CapabilityManifest(
                capability_id=VM_INVENTORY_CAPABILITY_ID,
                version="1.0.0",
                description="Read the virtual machines visible to this vCenter Server.",
                capability_class=CapabilityClass.C1_READ_ONLY,
                side_effects=frozenset({SideEffect.READ}),
                target_types=("target.hypervisor.vcenter",),
                timeout_seconds=60,
                idempotency=IdempotencyClass.SAFE,
            ),
        ),
        generated=True,
    )
