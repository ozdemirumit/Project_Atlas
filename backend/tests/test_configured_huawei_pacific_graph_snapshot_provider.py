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
    HuaweiPacificConnectionTestTransportFactory,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.huawei_pacific.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.huawei_pacific.ports import HuaweiPacificTransport
from atlas.modules.connectors.vendors.huawei_pacific.synthetic import (
    SyntheticHuaweiPacificResponse,
    SyntheticHuaweiPacificTransport,
)
from atlas.modules.graph.adapters.configured_huawei_pacific import (
    ConfiguredHuaweiPacificGraphSnapshotProvider,
)
from atlas.modules.graph.domain.models import EntityType
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.huawei-pacific-graph"
CLUSTER_SERVERS_PATH = "/api/v2/cluster/servers"


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
    def __init__(self, transport: SyntheticHuaweiPacificTransport) -> None:
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
    ) -> HuaweiPacificTransport:
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
    routes: Mapping[str, SyntheticHuaweiPacificResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredHuaweiPacificGraphSnapshotProvider, SyntheticHuaweiPacificTransport]:
    transport = SyntheticHuaweiPacificTransport(routes or {})
    provider = ConfiguredHuaweiPacificGraphSnapshotProvider(
        configuration_repository=cast(
            BundledConnectionConfigurationRepository, ScopeRepository(configurations)
        ),
        instance_repository=cast(ConnectorInstanceRepository, ScopeRepository(instances)),
        inventory_repository=cast(InventoryDeviceRepository, ScopeRepository(devices)),
        credential_materializer=cast(
            ConnectorCredentialMaterializer,
            CredentialMaterializer(available=credentials_available),
        ),
        transport_factory=cast(
            HuaweiPacificConnectionTestTransportFactory, TransportFactory(transport)
        ),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        runtime_state_repository=runtime_state_repository,
    )
    return provider, transport


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        configuration_id="connection_configuration.huawei-pacific-graph",
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        hostname="pacific.example.internal",
        port=8088,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.huawei.pacific.readonly",
    )


def _instance() -> SimpleNamespace:
    return SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        instance_state=DISABLED_UNCONFIGURED,
    )


def _device() -> SimpleNamespace:
    return SimpleNamespace(
        device_type=InventoryDeviceType.STORAGE,
        vendor="Huawei",
        serial_number="pacific-cluster-01",
        lifecycle=InventoryDeviceLifecycle.ACTIVE,
    )


@pytest.mark.asyncio
async def test_snapshot_is_empty_without_one_configured_instance() -> None:
    provider, transport = build_provider()

    snapshot = await provider.get_snapshot()

    assert snapshot.entities == ()
    assert snapshot.completeness == "unavailable"
    assert "single active configured Huawei Pacific MCP" in snapshot.known_gaps[0]
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
async def test_snapshot_maps_real_nodes_into_one_storage_system_entity() -> None:
    routes = {
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
                    }
                ],
            }
        )
    }
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    snapshot = await provider.get_snapshot()

    assert snapshot.data_profile == "configured_huawei_pacific_read_only"
    assert len(snapshot.entities) == 1
    assert snapshot.entities[0].entity_type is EntityType.STORAGE_SYSTEM
    assert snapshot.entities[0].vendor == "Huawei"
    assert snapshot.relationships == ()
    assert transport.requests == [CLUSTER_SERVERS_PATH]


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_huawei_pacific() -> None:
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
