from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.adapters.memory import InMemoryConnectorRegistryRepository
from atlas.modules.connectors.application.registry import (
    PACKAGE_REGISTER,
    ConnectorAccessContext,
    ConnectorRegistryService,
    FoundationConnectorValidator,
)
from atlas.modules.connectors.domain.models import (
    ConnectorHealth,
    ConnectorInstance,
    InstanceLifecycle,
    PackageLifecycle,
    SideEffect,
)
from atlas.modules.connectors.vendors.vcenter.client import VCenterClient, VCenterConnectorError
from atlas.modules.connectors.vendors.vcenter.domain import (
    VCenterHostConnectionState,
    VCenterHostPowerState,
    VCenterVmPowerState,
)
from atlas.modules.connectors.vendors.vcenter.manifest import (
    CLUSTER_INVENTORY_CAPABILITY_ID,
    HOST_INVENTORY_CAPABILITY_ID,
    VM_INVENTORY_CAPABILITY_ID,
    build_candidate_manifest,
)
from atlas.modules.connectors.vendors.vcenter.synthetic import (
    SyntheticVCenterFault,
    SyntheticVCenterResponse,
    SyntheticVCenterTransport,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.vcenter.lab"
HOST_PATH = "/api/vcenter/host"
CLUSTER_PATH = "/api/vcenter/cluster"
VM_PATH = "/api/vcenter/vm"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def access_context() -> ConnectorAccessContext:
    return ConnectorAccessContext(
        subject_id="subject.test.virtualization-engineer",
        actor_type="human",
        authentication_method="development",
        assurance_level="development",
        organization_id="organization.test",
        environment_id="environment.lab",
        site_id="site.virtualization-lab",
        target_id="target.vcenter.lab",
        correlation_id="cor_vcenter_candidate",
        permissions=frozenset({PACKAGE_REGISTER}),
    )


def connector_instance() -> ConnectorInstance:
    return ConnectorInstance(
        instance_id=INSTANCE_ID,
        package_id="connector.vmware.vcenter.automation-api",
        package_version="0.1.0",
        organization_id="organization.test",
        environment_id="environment.lab",
        site_id="site.virtualization-lab",
        target_id="target.vcenter.lab",
        enabled_capability_ids=frozenset(
            {
                HOST_INVENTORY_CAPABILITY_ID,
                CLUSTER_INVENTORY_CAPABILITY_ID,
                VM_INVENTORY_CAPABILITY_ID,
            }
        ),
        secret_reference_ids=("secret.vmware.vcenter.read-only",),
        lifecycle=InstanceLifecycle.DISABLED,
        health=ConnectorHealth.UNKNOWN,
        configuration_revision=1,
        created_at=NOW,
        created_by="subject.test.virtualization-engineer",
    )


def client(
    routes: dict[str, SyntheticVCenterResponse], **limits: int
) -> tuple[VCenterClient, SyntheticVCenterTransport]:
    transport = SyntheticVCenterTransport(routes)
    return VCenterClient(transport=transport, clock=lambda: NOW, **limits), transport


@pytest.mark.asyncio
async def test_candidate_manifest_is_c1_and_remains_quarantined() -> None:
    package_manifest = build_candidate_manifest(
        digest_sha256="a" * 64,
        network_destination="vcenter.lab.example:443",
    )
    assert package_manifest.generated is True
    assert {capability.capability_class for capability in package_manifest.capabilities} == {
        CapabilityClass.C1_READ_ONLY
    }
    assert {
        effect for capability in package_manifest.capabilities for effect in capability.side_effects
    } == {SideEffect.READ}

    repository = InMemoryConnectorRegistryRepository()
    service = ConnectorRegistryService(
        repository=repository,
        audit_sink=CollectingAuditSink(),
        validator=FoundationConnectorValidator(clock=lambda: NOW),
        clock=lambda: NOW,
    )
    package = await service.register_package(package_manifest, access_context())

    assert package.lifecycle is PackageLifecycle.QUARANTINED
    with pytest.raises(ValueError, match="approved host and port"):
        build_candidate_manifest(
            digest_sha256="b" * 64,
            network_destination="vcenter.lab.example:443/path",
        )


@pytest.mark.asyncio
async def test_host_inventory_reads_real_fields() -> None:
    connector, transport = client(
        {
            HOST_PATH: SyntheticVCenterResponse(
                payload=[
                    {
                        "host": "host-21",
                        "name": "esxi-01.lab.example",
                        "connection_state": "CONNECTED",
                        "power_state": "POWERED_ON",
                    },
                    {
                        "host": "host-22",
                        "name": "esxi-02.lab.example",
                        "connection_state": "NOT_RESPONDING",
                        "power_state": "POWERED_ON",
                    },
                ]
            )
        }
    )

    inventory = await connector.read_host_inventory()

    assert [host.host_id for host in inventory.hosts] == ["host-21", "host-22"]
    assert inventory.hosts[0].connection_state is VCenterHostConnectionState.CONNECTED
    assert inventory.hosts[0].power_state is VCenterHostPowerState.POWERED_ON
    assert inventory.hosts[1].connection_state is VCenterHostConnectionState.NOT_RESPONDING
    assert inventory.evidence_references[0].startswith("vcenter://vcenter/host#sha256:")
    assert transport.requests == [HOST_PATH]


@pytest.mark.asyncio
async def test_cluster_inventory_reads_real_fields() -> None:
    connector, transport = client(
        {
            CLUSTER_PATH: SyntheticVCenterResponse(
                payload=[
                    {
                        "cluster": "domain-c8",
                        "name": "Cluster-A",
                        "ha_enabled": True,
                        "drs_enabled": True,
                    }
                ]
            )
        }
    )

    inventory = await connector.read_cluster_inventory()

    assert inventory.clusters[0].cluster_id == "domain-c8"
    assert inventory.clusters[0].ha_enabled is True
    assert inventory.clusters[0].drs_enabled is True
    assert transport.requests == [CLUSTER_PATH]


@pytest.mark.asyncio
async def test_cluster_membership_reads_host_ids_via_the_confirmed_filter() -> None:
    membership_path = "/api/vcenter/host?filter.clusters=domain-c8"
    connector, transport = client(
        {
            membership_path: SyntheticVCenterResponse(
                payload=[
                    {
                        "host": "host-21",
                        "name": "esxi-01.lab.example",
                        "connection_state": "CONNECTED",
                        "power_state": "POWERED_ON",
                    }
                ]
            )
        }
    )

    result = await connector.read_cluster_membership("domain-c8")

    assert result.cluster_id == "domain-c8"
    assert result.host_ids == ("host-21",)
    assert transport.requests == [membership_path]


@pytest.mark.asyncio
async def test_cluster_membership_rejects_an_unsafe_cluster_identifier() -> None:
    connector, transport = client({})

    with pytest.raises(VCenterConnectorError) as error:
        await connector.read_cluster_membership("domain-c8/../etc")

    assert error.value.code == "malformed_vendor_response"
    assert transport.requests == []


@pytest.mark.asyncio
async def test_vm_inventory_reads_real_fields() -> None:
    connector, transport = client(
        {
            VM_PATH: SyntheticVCenterResponse(
                payload=[
                    {
                        "vm": "vm-1650",
                        "name": "test-vm-1",
                        "power_state": "POWERED_ON",
                        "cpu_count": 2,
                        "memory_size_MiB": 4096,
                    }
                ]
            )
        }
    )

    inventory = await connector.read_vm_inventory()

    assert inventory.virtual_machines[0].vm_id == "vm-1650"
    assert inventory.virtual_machines[0].power_state is VCenterVmPowerState.POWERED_ON
    assert inventory.virtual_machines[0].cpu_count == 2
    assert inventory.virtual_machines[0].memory_size_mib == 4096
    assert transport.requests == [VM_PATH]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fault", "code", "retryable"),
    [
        (SyntheticVCenterFault.DENIED, "vendor_permission_denied", False),
        (SyntheticVCenterFault.TIMEOUT, "target_timeout", True),
        (SyntheticVCenterFault.THROTTLED, "vendor_rate_limited", True),
        (SyntheticVCenterFault.UNAVAILABLE, "target_unavailable", True),
    ],
)
async def test_transport_faults_are_mapped_safely(
    fault: SyntheticVCenterFault, code: str, retryable: bool
) -> None:
    connector, _transport = client({HOST_PATH: SyntheticVCenterResponse(fault=fault)})

    with pytest.raises(VCenterConnectorError) as error:
        await connector.read_host_inventory()

    assert error.value.code == code
    assert error.value.retryable is retryable


@pytest.mark.asyncio
async def test_malformed_and_oversized_responses_are_rejected() -> None:
    malformed, _ = client({HOST_PATH: SyntheticVCenterResponse(payload=[{"host": 1}])})
    oversized, _ = client(
        {
            HOST_PATH: SyntheticVCenterResponse(
                payload=[
                    {
                        "host": "host-21",
                        "name": "esxi-01.lab.example",
                        "connection_state": "CONNECTED",
                        "power_state": "POWERED_ON",
                    },
                    {
                        "host": "host-22",
                        "name": "esxi-02.lab.example",
                        "connection_state": "CONNECTED",
                        "power_state": "POWERED_ON",
                    },
                ]
            )
        },
        maximum_hosts=1,
    )
    oversized_bytes, _ = client(
        {HOST_PATH: SyntheticVCenterResponse(payload=[{"padding": "x" * 128}])},
        maximum_response_bytes=64,
    )

    with pytest.raises(VCenterConnectorError) as malformed_error:
        await malformed.read_host_inventory()
    with pytest.raises(VCenterConnectorError) as oversized_error:
        await oversized.read_host_inventory()
    with pytest.raises(VCenterConnectorError) as oversized_bytes_error:
        await oversized_bytes.read_host_inventory()

    assert malformed_error.value.code == "malformed_vendor_response"
    assert oversized_error.value.code == "vendor_response_limit_exceeded"
    assert oversized_bytes_error.value.code == "vendor_response_limit_exceeded"


@pytest.mark.asyncio
async def test_self_test_uses_host_inventory_and_detects_incompatible_instance() -> None:
    # vCenter's list endpoints always return a JSON array at the top level (enforced by
    # VCenterClient._bounded before self_test ever inspects the payload), so unlike the Huawei
    # connectors' dict-wrapped responses there is no "compatible envelope, wrong inner shape"
    # case to distinguish here -- a successful read is always HEALTHY. The instance-package
    # mismatch path is what remains to exercise.
    compatible_transport = SyntheticVCenterTransport(
        {HOST_PATH: SyntheticVCenterResponse(payload=[])}
    )
    unavailable_transport = SyntheticVCenterTransport({})

    compatible = await VCenterClient(transport=compatible_transport, clock=lambda: NOW).self_test(
        connector_instance()
    )
    mismatched = await VCenterClient(transport=unavailable_transport, clock=lambda: NOW).self_test(
        replace(connector_instance(), package_id="connector.other")
    )

    assert compatible.health is ConnectorHealth.HEALTHY
    assert compatible_transport.requests == [HOST_PATH]
    assert mismatched.health is ConnectorHealth.INCOMPATIBLE
    assert mismatched.code == "connector_instance_package_mismatch"
    assert unavailable_transport.requests == []


def test_synthetic_transport_has_no_external_or_secret_access() -> None:
    transport = SyntheticVCenterTransport({HOST_PATH: SyntheticVCenterResponse(payload=[])})

    assert transport.network_access is False
    assert transport.secret_access is False


def test_candidate_package_assets_are_strict_and_synthetic_only() -> None:
    package_root = Path(__file__).parents[2] / "mcp" / "connectors" / "vcenter"
    schema = json.loads((package_root / "configuration.schema.json").read_text(encoding="utf-8"))
    provenance = json.loads((package_root / "source-provenance.json").read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert "credential_reference_id" in schema["required"]
    assert "password" not in schema["properties"]
    assert "username" not in schema["properties"]
    assert provenance["data_policy"] == "synthetic-only"
    assert provenance["production_credentials_present"] is False
    assert {source["method"] for source in provenance["capability_sources"]} == {"GET"}
