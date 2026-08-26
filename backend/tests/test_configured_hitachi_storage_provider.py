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
    HitachiConnectionTestTransportFactory,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.hitachi_ops_center.ports import HitachiOpsCenterTransport
from atlas.modules.connectors.vendors.hitachi_ops_center.synthetic import (
    SyntheticHitachiResponse,
    SyntheticHitachiTransport,
)
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType
from atlas.modules.storage.adapters.configured_hitachi import ConfiguredHitachiStorageProvider
from atlas.modules.storage.domain.models import InvestigationState, StorageHealthState

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.hitachi-health"
STORAGE_ID = "836000123456"
OTHER_STORAGE_ID = "A34000800556"


class ScopeRepository[T]:
    def __init__(self, records: Iterable[T]) -> None:
        self.records = tuple(records)

    async def list_scope(self, **_kwargs: object) -> tuple[T, ...]:
        return self.records


class AuthorizationHeaderLease:
    @staticmethod
    def authorization_header() -> str:
        return "Basic hidden"


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
    def __init__(self, transport: SyntheticHitachiTransport) -> None:
        self.transport = transport

    def create(
        self,
        *,
        hostname: str,
        port: int,
        trust_profile_id: str,
        authorization_header_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> HitachiOpsCenterTransport:
        del (
            hostname,
            port,
            trust_profile_id,
            authorization_header_provider,
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
    routes: Mapping[str, SyntheticHitachiResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredHitachiStorageProvider, SyntheticHitachiTransport]:
    transport = SyntheticHitachiTransport(routes or {})
    provider = ConfiguredHitachiStorageProvider(
        configuration_repository=cast(
            BundledConnectionConfigurationRepository, ScopeRepository(configurations)
        ),
        instance_repository=cast(ConnectorInstanceRepository, ScopeRepository(instances)),
        inventory_repository=cast(InventoryDeviceRepository, ScopeRepository(devices)),
        credential_materializer=cast(
            ConnectorCredentialMaterializer,
            CredentialMaterializer(available=credentials_available),
        ),
        transport_factory=cast(HitachiConnectionTestTransportFactory, TransportFactory(transport)),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        runtime_state_repository=runtime_state_repository,
    )
    return provider, transport


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        configuration_id="connection_configuration.hitachi-storage",
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        hostname="opscenter.example.internal",
        port=23450,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.hitachi.readonly",
    )


def _instance() -> SimpleNamespace:
    return SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        instance_state=DISABLED_UNCONFIGURED,
    )


def _device(storage_id: str = STORAGE_ID) -> SimpleNamespace:
    return SimpleNamespace(
        device_type=InventoryDeviceType.STORAGE,
        vendor="Hitachi Vantara",
        serial_number=storage_id,
        lifecycle=InventoryDeviceLifecycle.ACTIVE,
    )


@pytest.mark.asyncio
async def test_overview_reports_unavailable_without_one_configured_instance() -> None:
    provider, transport = build_provider()

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.assets == ()
    assert overview.investigation.state is InvestigationState.INCONCLUSIVE
    assert "single active configured Hitachi MCP" in overview.investigation.summary
    assert transport.requests == []
    assert len(overview.evidence) == 1


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
async def test_overview_reports_unavailable_without_allowlisted_storage() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.assets == ()
    assert "No active Hitachi storage serial number" in overview.investigation.summary
    assert transport.requests == []


@pytest.mark.asyncio
async def test_overview_maps_real_inventory_and_health_into_assets_and_findings() -> None:
    routes = {
        "/v1/objects/storages": SyntheticHitachiResponse(
            payload={
                "data": [
                    {
                        "storageDeviceId": STORAGE_ID,
                        "model": "VSP G400",
                        "serialNumber": 123456,
                    },
                    {
                        "storageDeviceId": OTHER_STORAGE_ID,
                        "model": "VSP One B28",
                        "serialNumber": 800556,
                    },
                ]
            }
        ),
        f"/v1/objects/storages/{STORAGE_ID}/components/instance": SyntheticHitachiResponse(
            payload={"ctls": [{"location": "CTL1", "status": "Normal"}]}
        ),
        f"/v1/objects/storages/{OTHER_STORAGE_ID}/components/instance": SyntheticHitachiResponse(
            payload={"ctls": [{"location": "CTL01", "status": "Warning"}]}
        ),
    }
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(STORAGE_ID), _device(OTHER_STORAGE_ID)),
        routes=routes,
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.data_profile == "configured_hitachi_read_only"
    assert len(overview.assets) == 2
    assert {asset.health for asset in overview.assets} == {
        StorageHealthState.HEALTHY,
        StorageHealthState.WARNING,
    }
    assert len(overview.findings) == 1
    assert overview.findings[0].severity.value == "warning"
    evidence_ids = {item.reference for item in overview.evidence}
    referenced = {reference for asset in overview.assets for reference in asset.evidence_references}
    assert referenced <= evidence_ids
    assert transport.requests == [
        "/v1/objects/storages",
        f"/v1/objects/storages/{STORAGE_ID}/components/instance",
        f"/v1/objects/storages/{OTHER_STORAGE_ID}/components/instance",
    ]


@pytest.mark.asyncio
async def test_overview_marks_asset_unknown_when_hardware_health_read_fails_for_one_array() -> None:
    routes = {
        "/v1/objects/storages": SyntheticHitachiResponse(
            payload={
                "data": [
                    {
                        "storageDeviceId": STORAGE_ID,
                        "model": "VSP G400",
                        "serialNumber": 123456,
                    },
                    {
                        "storageDeviceId": OTHER_STORAGE_ID,
                        "model": "VSP One B28",
                        "serialNumber": 800556,
                    },
                ]
            }
        ),
        f"/v1/objects/storages/{STORAGE_ID}/components/instance": SyntheticHitachiResponse(
            payload={"ctls": [{"location": "CTL1", "status": "Normal"}]}
        ),
    }
    provider, _transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(STORAGE_ID), _device(OTHER_STORAGE_ID)),
        routes=routes,
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert len(overview.assets) == 2
    unknown_assets = [
        asset for asset in overview.assets if asset.health is StorageHealthState.UNKNOWN
    ]
    assert len(unknown_assets) == 1
    assert unknown_assets[0].storage_device_id == OTHER_STORAGE_ID
    assert any(
        "could not be read for 1 of 2" in unknown for unknown in overview.investigation.unknowns
    )
    healthy_assets = [
        asset for asset in overview.assets if asset.health is StorageHealthState.HEALTHY
    ]
    assert len(healthy_assets) == 1


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_hitachi() -> None:
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

    provider = ConfiguredHitachiStorageProvider(
        configuration_repository=cast(
            BundledConnectionConfigurationRepository, ScopeRepository((_configuration(),))
        ),
        instance_repository=cast(ConnectorInstanceRepository, ScopeRepository((_instance(),))),
        inventory_repository=cast(InventoryDeviceRepository, ScopeRepository((_device(),))),
        credential_materializer=cast(
            ConnectorCredentialMaterializer, RaisingCredentialMaterializer()
        ),
        transport_factory=cast(
            HitachiConnectionTestTransportFactory, TransportFactory(SyntheticHitachiTransport({}))
        ),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.assets == ()
    assert overview.investigation.state is InvestigationState.INCONCLUSIVE
