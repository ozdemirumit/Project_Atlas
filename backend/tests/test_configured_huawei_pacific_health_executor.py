from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
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
    SyntheticHuaweiPacificFault,
    SyntheticHuaweiPacificResponse,
    SyntheticHuaweiPacificTransport,
)
from atlas.modules.health_checks.adapters.configured_huawei_pacific import (
    ConfiguredHuaweiPacificHealthExecutor,
)
from atlas.modules.health_checks.adapters.synthetic import (
    SyntheticStorageHealthExecutor,
    build_synthetic_health_check_definitions,
)
from atlas.modules.health_checks.domain.models import HealthCheckDefinition, HealthCheckRunState
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.huawei-pacific-health"
CLUSTER_SERVERS_PATH = "/api/v2/cluster/servers"
STORAGE_POOL_PATH = "/api/v2/data_service/storagepool"


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


def definitions() -> tuple[HealthCheckDefinition, HealthCheckDefinition]:
    (
        _controller,
        _capacity,
        _fabric,
        _huawei_controller,
        _huawei_capacity,
        node,
        capacity,
        _vcenter_host,
        _commvault_job,
    ) = build_synthetic_health_check_definitions(
        organization_id="organization.atlas.local",
        environment="development",
        anchor_at=NOW,
    )
    return (
        replace(
            node,
            connector_id=PACKAGE_ID,
            connector_version="0.1.0",
            target_id="target.huawei.pacific.configured",
        ),
        replace(
            capacity,
            connector_id=PACKAGE_ID,
            connector_version="0.1.0",
            target_id="target.huawei.pacific.configured",
        ),
    )


def build_executor(
    *,
    configurations: Iterable[object] = (),
    instances: Iterable[object] = (),
    devices: Iterable[object] = (),
    credentials_available: bool = True,
    routes: Mapping[str, SyntheticHuaweiPacificResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredHuaweiPacificHealthExecutor, SyntheticHuaweiPacificTransport]:
    transport = SyntheticHuaweiPacificTransport(routes or {})
    executor = ConfiguredHuaweiPacificHealthExecutor(
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
        fallback_executor=SyntheticStorageHealthExecutor(),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        runtime_state_repository=runtime_state_repository,
    )
    return executor, transport


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        configuration_id="connection_configuration.huawei-pacific-health",
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
async def test_node_check_fails_safely_without_one_configured_instance() -> None:
    executor, transport = build_executor()
    node, _capacity = definitions()

    result = await executor.execute(node, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert transport.requests == []
    assert "single active configured Huawei Pacific MCP" in result.partial_reasons[0]


@pytest.mark.asyncio
async def test_node_check_does_not_contact_disabled_configured_mcp() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        runtime_state_repository=InMemoryBundledConnectorRuntimeStateRepository(),
    )
    node, _capacity = definitions()

    result = await executor.execute(node, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "must be enabled" in result.partial_reasons[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_node_check_uses_configured_read_only_huawei_pacific_transport() -> None:
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
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )
    node, _capacity = definitions()

    result = await executor.execute(node, started_at=NOW)

    assert result.state is HealthCheckRunState.COMPLETED
    assert transport.requests == [CLUSTER_SERVERS_PATH]
    assert result.observations[0].value == "normal"


@pytest.mark.asyncio
async def test_capacity_check_computes_utilization_from_raw_capacity() -> None:
    routes = {
        STORAGE_POOL_PATH: SyntheticHuaweiPacificResponse(
            payload={
                "storagePools": [
                    {
                        "storagePoolId": 1,
                        "storagePoolName": "pool-1",
                        "status": "0",
                        "totalCapacity": 1000,
                        "usedCapacity": 220,
                    }
                ]
            }
        )
    }
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )
    _node, capacity = definitions()

    result = await executor.execute(capacity, started_at=NOW)

    assert result.state is HealthCheckRunState.COMPLETED
    assert result.observations[0].value == "22.0"
    assert transport.requests == [STORAGE_POOL_PATH]


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_huawei_pacific() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        credentials_available=False,
    )
    node, _capacity = definitions()

    result = await executor.execute(node, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "credential reference is unavailable" in result.partial_reasons[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_transport_fault_is_reported_safely() -> None:
    routes = {
        CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(
            fault=SyntheticHuaweiPacificFault.UNAVAILABLE
        )
    }
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )
    node, _capacity = definitions()

    result = await executor.execute(node, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "failed safely" in result.partial_reasons[0]
    assert transport.requests == [CLUSTER_SERVERS_PATH]


@pytest.mark.asyncio
async def test_other_definitions_are_delegated_to_the_fallback_executor() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
    )
    (
        hitachi_controller,
        _capacity,
        _fabric,
        _hc,
        _hcap,
        _node,
        _pacific_capacity,
        _vcenter_host,
        _commvault_job,
    ) = build_synthetic_health_check_definitions(
        organization_id="organization.atlas.local",
        environment="development",
        anchor_at=NOW,
    )

    result = await executor.execute(hitachi_controller, started_at=NOW)

    assert result.state in {HealthCheckRunState.COMPLETED, HealthCheckRunState.PARTIAL}
    assert transport.requests == []
