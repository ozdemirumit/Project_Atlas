from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from atlas.modules.connectors.adapters.bundled_runtime_state_memory import (
    InMemoryBundledConnectorRuntimeStateRepository,
)
from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.application.bundled_runtime_state_ports import (
    BundledConnectorRuntimeStateRepository,
)
from atlas.modules.connectors.application.connection_test_ports import (
    ConnectorAuthorizationHeaderLease,
    ConnectorConnectionTestError,
    ConnectorCredentialMaterializer,
    VCenterConnectionTestTransportFactory,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.vcenter.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.vcenter.ports import VCenterTransport
from atlas.modules.connectors.vendors.vcenter.synthetic import (
    SyntheticVCenterResponse,
    SyntheticVCenterTransport,
)
from atlas.modules.graph.adapters.configured_vcenter import ConfiguredVCenterGraphSnapshotProvider
from atlas.modules.graph.domain.models import EntityType
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.vcenter-graph"
HOST_PATH = "/api/vcenter/host"
CLUSTER_PATH = "/api/vcenter/cluster"
VM_PATH = "/api/vcenter/vm"


class ScopeRepository[T]:
    def __init__(self, records: Iterable[T]) -> None:
        self.records = tuple(records)

    async def list_scope(self, **_kwargs: object) -> tuple[T, ...]:
        return self.records


class AuthorizationHeaderLease:
    @staticmethod
    def authorization_header() -> str:
        return "operator:hidden"


class CredentialMaterializer:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available

    @asynccontextmanager
    async def lease_authorization_header(
        self,
        *,
        secret_reference_id: str,
        maximum_lease_seconds: int,
    ) -> AsyncIterator[ConnectorAuthorizationHeaderLease]:
        del secret_reference_id, maximum_lease_seconds
        if not self.available:
            raise ConnectorConnectionTestError("connection_test_credentials_unavailable")
        yield AuthorizationHeaderLease()


class TransportFactory:
    def __init__(self, transport: SyntheticVCenterTransport) -> None:
        self.transport = transport

    def create(
        self,
        *,
        hostname: str,
        port: int,
        trust_profile_id: str,
        credential_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> VCenterTransport:
        del (
            hostname,
            port,
            trust_profile_id,
            credential_provider,
            timeout_seconds,
            maximum_response_bytes,
        )
        return self.transport


def build_provider(
    *,
    configurations: Iterable[object] = (),
    instances: Iterable[object] = (),
    devices: Iterable[object] = (),
    credentials_available: bool = True,
    routes: Mapping[str, SyntheticVCenterResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredVCenterGraphSnapshotProvider, SyntheticVCenterTransport]:
    transport = SyntheticVCenterTransport(dict(routes or {}))
    provider = ConfiguredVCenterGraphSnapshotProvider(
        configuration_repository=cast(
            BundledConnectionConfigurationRepository, ScopeRepository(configurations)
        ),
        instance_repository=cast(ConnectorInstanceRepository, ScopeRepository(instances)),
        inventory_repository=cast(InventoryDeviceRepository, ScopeRepository(devices)),
        credential_materializer=cast(
            ConnectorCredentialMaterializer,
            CredentialMaterializer(available=credentials_available),
        ),
        transport_factory=cast(VCenterConnectionTestTransportFactory, TransportFactory(transport)),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        runtime_state_repository=runtime_state_repository,
    )
    return provider, transport


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        configuration_id="connection_configuration.vcenter-graph",
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        hostname="vcenter.example.internal",
        port=443,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.vmware.vcenter.readonly",
    )


def _instance() -> SimpleNamespace:
    return SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        instance_state=DISABLED_UNCONFIGURED,
    )


def _device() -> SimpleNamespace:
    return SimpleNamespace(
        device_type=InventoryDeviceType.VIRTUALIZATION,
        vendor="VMware",
        serial_number="vcenter-01",
        lifecycle=InventoryDeviceLifecycle.ACTIVE,
    )


def _routes() -> dict[str, SyntheticVCenterResponse]:
    return {
        HOST_PATH: SyntheticVCenterResponse(
            payload=[
                {
                    "host": "host-21",
                    "name": "esxi-01.lab.example",
                    "connection_state": "CONNECTED",
                    "power_state": "POWERED_ON",
                }
            ]
        ),
        CLUSTER_PATH: SyntheticVCenterResponse(
            payload=[
                {
                    "cluster": "domain-c8",
                    "name": "Cluster-A",
                    "ha_enabled": True,
                    "drs_enabled": True,
                }
            ]
        ),
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
        ),
    }


@pytest.mark.asyncio
async def test_snapshot_is_empty_without_one_configured_instance() -> None:
    provider, transport = build_provider()

    snapshot = await provider.get_snapshot()

    assert snapshot.entities == ()
    assert snapshot.completeness == "unavailable"
    assert "single active configured vCenter MCP" in snapshot.known_gaps[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_snapshot_is_empty_when_configured_mcp_disabled() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        runtime_state_repository=InMemoryBundledConnectorRuntimeStateRepository(),
    )

    snapshot = await provider.get_snapshot()

    assert snapshot.entities == ()
    assert "must be enabled" in snapshot.known_gaps[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_snapshot_is_empty_without_allowlisted_vcenter() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
    )

    snapshot = await provider.get_snapshot()

    assert snapshot.entities == ()
    assert "No active vCenter Server" in snapshot.known_gaps[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_snapshot_maps_hosts_clusters_and_vms_as_entities_only() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=_routes(),
    )

    snapshot = await provider.get_snapshot()

    assert snapshot.data_profile == "configured_vcenter_read_only"
    entity_types = {entity.entity_type for entity in snapshot.entities}
    assert entity_types == {
        EntityType.HYPERVISOR_HOST,
        EntityType.HYPERVISOR_CLUSTER,
        EntityType.VIRTUAL_MACHINE,
    }
    assert len(snapshot.entities) == 3
    assert snapshot.relationships == ()
    assert transport.requests == [HOST_PATH, CLUSTER_PATH, VM_PATH]


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_vcenter() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        credentials_available=False,
    )

    snapshot = await provider.get_snapshot()

    assert snapshot.entities == ()
    assert "credential reference is unavailable" in snapshot.known_gaps[0]
    assert transport.requests == []
