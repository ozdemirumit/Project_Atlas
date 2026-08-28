from __future__ import annotations

import json
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
from atlas.modules.connectors.vendors.huawei_pacific.client import (
    HuaweiPacificClient,
    HuaweiPacificConnectorError,
)
from atlas.modules.connectors.vendors.huawei_pacific.domain import (
    HuaweiPacificNodeRunningStatus,
    HuaweiPacificPoolStatus,
)
from atlas.modules.connectors.vendors.huawei_pacific.manifest import (
    CLUSTER_NODE_CAPABILITY_ID,
    STORAGE_POOL_CAPABILITY_ID,
    build_candidate_manifest,
)
from atlas.modules.connectors.vendors.huawei_pacific.synthetic import (
    SyntheticHuaweiPacificFault,
    SyntheticHuaweiPacificResponse,
    SyntheticHuaweiPacificTransport,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.huawei-pacific.lab"
CLUSTER_SERVERS_PATH = "/api/v2/cluster/servers"
STORAGE_POOL_PATH = "/api/v2/data_service/storagepool"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def access_context() -> ConnectorAccessContext:
    return ConnectorAccessContext(
        subject_id="subject.test.storage-engineer",
        actor_type="human",
        authentication_method="development",
        assurance_level="development",
        organization_id="organization.test",
        environment_id="environment.lab",
        site_id="site.storage-lab",
        target_id="target.huawei.pacific.lab",
        correlation_id="cor_huawei_pacific_candidate",
        permissions=frozenset({PACKAGE_REGISTER}),
    )


def connector_instance() -> ConnectorInstance:
    return ConnectorInstance(
        instance_id=INSTANCE_ID,
        package_id="connector.huawei.pacific.cluster-manager",
        package_version="0.1.0",
        organization_id="organization.test",
        environment_id="environment.lab",
        site_id="site.storage-lab",
        target_id="target.huawei.pacific.lab",
        enabled_capability_ids=frozenset({CLUSTER_NODE_CAPABILITY_ID, STORAGE_POOL_CAPABILITY_ID}),
        secret_reference_ids=("secret.huawei.pacific.read-only",),
        lifecycle=InstanceLifecycle.DISABLED,
        health=ConnectorHealth.UNKNOWN,
        configuration_revision=1,
        created_at=NOW,
        created_by="subject.test.storage-engineer",
    )


def client(
    routes: dict[str, SyntheticHuaweiPacificResponse], **limits: int
) -> tuple[HuaweiPacificClient, SyntheticHuaweiPacificTransport]:
    transport = SyntheticHuaweiPacificTransport(routes)
    return HuaweiPacificClient(transport=transport, clock=lambda: NOW, **limits), transport


@pytest.mark.asyncio
async def test_candidate_manifest_is_c1_and_remains_quarantined() -> None:
    package_manifest = build_candidate_manifest(
        digest_sha256="a" * 64,
        network_destination="pacific.lab.example:8088",
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
            network_destination="pacific.lab.example:8088/path",
        )


@pytest.mark.asyncio
async def test_cluster_inventory_reads_real_node_fields() -> None:
    connector, transport = client(
        {
            CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(
                payload={
                    "result": {"code": 0},
                    "data": [
                        {
                            "id": "node1",
                            "name": "node-1",
                            "management_ip": "192.0.2.10",
                            "model": "Pacific 9550",
                            "running_status": "online",
                            "in_cluster": True,
                        },
                        {
                            "id": "node2",
                            "name": "node-2",
                            "management_ip": "192.0.2.11",
                            "model": "Pacific 9550",
                            "running_status": "offline",
                            "in_cluster": True,
                        },
                    ],
                }
            )
        }
    )

    inventory = await connector.read_cluster_inventory()

    assert [node.node_id for node in inventory.nodes] == ["node1", "node2"]
    assert inventory.nodes[0].running_status is HuaweiPacificNodeRunningStatus.ONLINE
    assert inventory.nodes[1].running_status is HuaweiPacificNodeRunningStatus.OFFLINE
    assert inventory.evidence_references[0].startswith("huawei-pacific://cluster/servers#sha256:")
    assert transport.requests == [CLUSTER_SERVERS_PATH]


@pytest.mark.asyncio
async def test_pool_capacity_reads_pools_and_computes_utilization() -> None:
    connector, transport = client(
        {
            STORAGE_POOL_PATH: SyntheticHuaweiPacificResponse(
                payload={
                    "storagePools": [
                        {
                            "storagePoolId": 1,
                            "storagePoolName": "pool-1",
                            "status": "0",
                            "totalCapacity": 1000,
                            "usedCapacity": 780,
                        }
                    ]
                }
            )
        }
    )

    pools = await connector.read_pool_capacity()

    assert pools[0].pool_id == "1"
    assert pools[0].status is HuaweiPacificPoolStatus.NORMAL
    assert pools[0].used_capacity_percent == 78.0
    assert transport.requests == [STORAGE_POOL_PATH]


@pytest.mark.asyncio
async def test_vendor_logical_error_is_reported_safely_despite_http_200() -> None:
    connector, transport = client(
        {
            CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(
                payload={"result": {"code": 123, "description": "x"}}
            )
        }
    )

    with pytest.raises(HuaweiPacificConnectorError) as error:
        await connector.read_cluster_inventory()

    assert error.value.code == "vendor_error_response"
    assert transport.requests == [CLUSTER_SERVERS_PATH]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fault", "code", "retryable"),
    [
        (SyntheticHuaweiPacificFault.DENIED, "vendor_permission_denied", False),
        (SyntheticHuaweiPacificFault.TIMEOUT, "target_timeout", True),
        (SyntheticHuaweiPacificFault.THROTTLED, "vendor_rate_limited", True),
        (SyntheticHuaweiPacificFault.UNAVAILABLE, "target_unavailable", True),
    ],
)
async def test_transport_faults_are_mapped_safely(
    fault: SyntheticHuaweiPacificFault, code: str, retryable: bool
) -> None:
    connector, _transport = client(
        {CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(fault=fault)}
    )

    with pytest.raises(HuaweiPacificConnectorError) as error:
        await connector.read_cluster_inventory()

    assert error.value.code == code
    assert error.value.retryable is retryable


@pytest.mark.asyncio
async def test_malformed_and_oversized_responses_are_rejected() -> None:
    malformed, _ = client(
        {CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(payload={"data": "invalid"})}
    )
    oversized, _ = client(
        {
            CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(
                payload={
                    "data": [
                        {
                            "id": "node1",
                            "name": "node-1",
                            "management_ip": "192.0.2.10",
                            "model": "Pacific 9550",
                            "running_status": "online",
                            "in_cluster": True,
                        },
                        {
                            "id": "node2",
                            "name": "node-2",
                            "management_ip": "192.0.2.11",
                            "model": "Pacific 9550",
                            "running_status": "online",
                            "in_cluster": True,
                        },
                    ]
                }
            )
        },
        maximum_nodes=1,
    )
    oversized_bytes, _ = client(
        {
            CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(
                payload={"data": [], "padding": "x" * 128}
            )
        },
        maximum_response_bytes=64,
    )

    with pytest.raises(HuaweiPacificConnectorError) as malformed_error:
        await malformed.read_cluster_inventory()
    with pytest.raises(HuaweiPacificConnectorError) as oversized_error:
        await oversized.read_cluster_inventory()
    with pytest.raises(HuaweiPacificConnectorError) as oversized_bytes_error:
        await oversized_bytes.read_cluster_inventory()

    assert malformed_error.value.code == "malformed_vendor_response"
    assert oversized_error.value.code == "vendor_response_limit_exceeded"
    assert oversized_bytes_error.value.code == "vendor_response_limit_exceeded"


@pytest.mark.asyncio
async def test_self_test_uses_cluster_servers_and_detects_incompatible_shape() -> None:
    compatible_transport = SyntheticHuaweiPacificTransport(
        {CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(payload={"data": []})}
    )
    incompatible_transport = SyntheticHuaweiPacificTransport(
        {CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(payload={"unexpected": True})}
    )

    compatible = await HuaweiPacificClient(
        transport=compatible_transport, clock=lambda: NOW
    ).self_test(connector_instance())
    incompatible = await HuaweiPacificClient(
        transport=incompatible_transport, clock=lambda: NOW
    ).self_test(connector_instance())

    assert compatible.health is ConnectorHealth.HEALTHY
    assert incompatible.health is ConnectorHealth.INCOMPATIBLE
    assert compatible_transport.requests == [CLUSTER_SERVERS_PATH]
    assert incompatible_transport.requests == [CLUSTER_SERVERS_PATH]


def test_synthetic_transport_has_no_external_or_secret_access() -> None:
    transport = SyntheticHuaweiPacificTransport(
        {CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(payload={"data": []})}
    )

    assert transport.network_access is False
    assert transport.secret_access is False


def test_candidate_package_assets_are_strict_and_synthetic_only() -> None:
    package_root = Path(__file__).parents[2] / "mcp" / "connectors" / "huawei_pacific"
    schema = json.loads((package_root / "configuration.schema.json").read_text(encoding="utf-8"))
    provenance = json.loads((package_root / "source-provenance.json").read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert "credential_reference_id" in schema["required"]
    assert "password" not in schema["properties"]
    assert "username" not in schema["properties"]
    assert provenance["data_policy"] == "synthetic-only"
    assert provenance["production_credentials_present"] is False
    assert {source["method"] for source in provenance["capability_sources"]} == {"GET"}
