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
    BrocadeConnectionTestTransportFactory,
    ConnectorAuthorizationHeaderLease,
    ConnectorConnectionTestError,
    ConnectorCredentialMaterializer,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.brocade_sannav.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.brocade_sannav.ports import BrocadeSanNavTransport
from atlas.modules.connectors.vendors.brocade_sannav.synthetic import (
    SyntheticBrocadeResponse,
    SyntheticBrocadeSanNavTransport,
)
from atlas.modules.graph.adapters.configured_brocade_sannav import (
    ConfiguredBrocadeSanNavGraphSnapshotProvider,
)
from atlas.modules.graph.domain.models import EntityType
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.brocade-graph"
FABRIC_WWN = "10:00:00:05:1e:35:1a:00"
FABRICS_PATH = "/external-api/v1/discovery/fabrics/"
FABRIC_MEMBERS_PATH = f"/external-api/v1/discovery/fabric-members/?principalSwitchWWN={FABRIC_WWN}"


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
    def __init__(self, transport: SyntheticBrocadeSanNavTransport) -> None:
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
    ) -> BrocadeSanNavTransport:
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
    routes: Mapping[str, SyntheticBrocadeResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredBrocadeSanNavGraphSnapshotProvider, SyntheticBrocadeSanNavTransport]:
    transport = SyntheticBrocadeSanNavTransport(routes or {})
    provider = ConfiguredBrocadeSanNavGraphSnapshotProvider(
        configuration_repository=cast(
            BundledConnectionConfigurationRepository, ScopeRepository(configurations)
        ),
        instance_repository=cast(ConnectorInstanceRepository, ScopeRepository(instances)),
        inventory_repository=cast(InventoryDeviceRepository, ScopeRepository(devices)),
        credential_materializer=cast(
            ConnectorCredentialMaterializer,
            CredentialMaterializer(available=credentials_available),
        ),
        transport_factory=cast(BrocadeConnectionTestTransportFactory, TransportFactory(transport)),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        runtime_state_repository=runtime_state_repository,
    )
    return provider, transport


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        configuration_id="connection_configuration.brocade-graph",
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        hostname="sannav.example.internal",
        port=443,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.brocade.readonly",
    )


def _instance() -> SimpleNamespace:
    return SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        instance_state=DISABLED_UNCONFIGURED,
    )


def _device(wwn: str = FABRIC_WWN) -> SimpleNamespace:
    return SimpleNamespace(
        device_type=InventoryDeviceType.SAN_SWITCH,
        vendor="Broadcom (Brocade)",
        serial_number=wwn,
        lifecycle=InventoryDeviceLifecycle.ACTIVE,
    )


@pytest.mark.asyncio
async def test_snapshot_is_empty_without_one_configured_instance() -> None:
    provider, transport = build_provider()

    snapshot = await provider.get_snapshot()

    assert snapshot.entities == ()
    assert snapshot.relationships == ()
    assert snapshot.completeness == "unavailable"
    assert "single active configured Brocade SANnav MCP" in snapshot.known_gaps[0]
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
async def test_snapshot_is_empty_without_allowlisted_fabric() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
    )

    snapshot = await provider.get_snapshot()

    assert snapshot.entities == ()
    assert "No active Brocade fabric principal switch WWN" in snapshot.known_gaps[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_snapshot_maps_real_inventory_into_san_switch_entities_with_no_relationships() -> (
    None
):
    routes = {
        FABRICS_PATH: SyntheticBrocadeResponse(
            payload={"Fabrics": [{"principalSwitchWwn": FABRIC_WWN, "name": "Fabric-A"}]}
        ),
        FABRIC_MEMBERS_PATH: SyntheticBrocadeResponse(
            payload={"Switches": [{"ipAddress": "192.0.2.10"}, {"ipAddress": "192.0.2.11"}]}
        ),
    }
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    snapshot = await provider.get_snapshot()

    assert snapshot.data_profile == "configured_brocade_sannav_read_only"
    assert len(snapshot.entities) == 2
    assert all(entity.entity_type is EntityType.SAN_SWITCH for entity in snapshot.entities)
    assert snapshot.relationships == ()
    evidence_ids = {item.reference for item in snapshot.evidence}
    referenced = {
        reference for entity in snapshot.entities for reference in entity.evidence_references
    }
    assert referenced <= evidence_ids
    assert transport.requests == [FABRICS_PATH, FABRIC_MEMBERS_PATH]
    assert any("no relationship to storage systems" in gap for gap in snapshot.known_gaps)


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_brocade() -> None:
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


@pytest.mark.asyncio
async def test_snapshot_never_raises_on_connector_timeout() -> None:
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

    provider = ConfiguredBrocadeSanNavGraphSnapshotProvider(
        configuration_repository=cast(
            BundledConnectionConfigurationRepository, ScopeRepository((_configuration(),))
        ),
        instance_repository=cast(ConnectorInstanceRepository, ScopeRepository((_instance(),))),
        inventory_repository=cast(InventoryDeviceRepository, ScopeRepository((_device(),))),
        credential_materializer=cast(
            ConnectorCredentialMaterializer, RaisingCredentialMaterializer()
        ),
        transport_factory=cast(
            BrocadeConnectionTestTransportFactory,
            TransportFactory(SyntheticBrocadeSanNavTransport({})),
        ),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
    )

    snapshot = await provider.get_snapshot()

    assert snapshot.entities == ()
    assert snapshot.completeness == "unavailable"
