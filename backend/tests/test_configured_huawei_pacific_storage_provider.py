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
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType
from atlas.modules.storage.adapters.configured_huawei_pacific import (
    ConfiguredHuaweiPacificStorageProvider,
)
from atlas.modules.storage.domain.models import InvestigationState, StorageHealthState

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.huawei-pacific-storage"
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
) -> tuple[ConfiguredHuaweiPacificStorageProvider, SyntheticHuaweiPacificTransport]:
    transport = SyntheticHuaweiPacificTransport(routes or {})
    provider = ConfiguredHuaweiPacificStorageProvider(
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
        configuration_id="connection_configuration.huawei-pacific-storage",
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
async def test_overview_reports_unavailable_without_one_configured_instance() -> None:
    provider, transport = build_provider()

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.assets == ()
    assert overview.investigation.state is InvestigationState.INCONCLUSIVE
    assert "single active configured Huawei Pacific MCP" in overview.investigation.summary
    assert transport.requests == []


@pytest.mark.asyncio
async def test_overview_reports_unavailable_when_configured_mcp_disabled() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        runtime_state_repository=InMemoryBundledConnectorRuntimeStateRepository(),
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.assets == ()
    assert "must be enabled" in overview.investigation.summary
    assert transport.requests == []


@pytest.mark.asyncio
async def test_overview_reports_unavailable_without_allowlisted_cluster() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.assets == ()
    assert "No active Huawei Pacific storage cluster" in overview.investigation.summary
    assert transport.requests == []


@pytest.mark.asyncio
async def test_overview_maps_real_nodes_into_one_asset_with_findings() -> None:
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
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.data_profile == "configured_huawei_pacific_read_only"
    assert len(overview.assets) == 1
    assert overview.assets[0].health is StorageHealthState.CRITICAL
    assert len(overview.findings) == 1
    assert overview.findings[0].severity.value == "critical"
    evidence_ids = {item.reference for item in overview.evidence}
    referenced = {reference for asset in overview.assets for reference in asset.evidence_references}
    assert referenced <= evidence_ids
    assert transport.requests == [CLUSTER_SERVERS_PATH]


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_huawei_pacific() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        credentials_available=False,
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.assets == ()
    assert "credential reference is unavailable" in overview.investigation.summary
    assert transport.requests == []


@pytest.mark.asyncio
async def test_overview_never_raises_on_connector_timeout() -> None:
    class RaisingLease:
        async def __aenter__(self) -> ConnectorAuthorizationHeaderLease:
            raise TimeoutError("simulated timeout")

        async def __aexit__(self, *exc_info: object) -> None:
            return None

    class RaisingCredentialMaterializer:
        def lease_authorization_header(
            self, *, secret_reference_id: str, maximum_lease_seconds: int
        ) -> RaisingLease:
            del secret_reference_id, maximum_lease_seconds
            return RaisingLease()

    provider = ConfiguredHuaweiPacificStorageProvider(
        configuration_repository=cast(
            BundledConnectionConfigurationRepository, ScopeRepository((_configuration(),))
        ),
        instance_repository=cast(ConnectorInstanceRepository, ScopeRepository((_instance(),))),
        inventory_repository=cast(InventoryDeviceRepository, ScopeRepository((_device(),))),
        credential_materializer=cast(
            ConnectorCredentialMaterializer, RaisingCredentialMaterializer()
        ),
        transport_factory=cast(
            HuaweiPacificConnectionTestTransportFactory,
            TransportFactory(SyntheticHuaweiPacificTransport({})),
        ),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.assets == ()
    assert overview.investigation.state is InvestigationState.INCONCLUSIVE
