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
from atlas.modules.health_checks.adapters.configured_hitachi import (
    ConfiguredHitachiHealthExecutor,
)
from atlas.modules.health_checks.adapters.synthetic import (
    SyntheticStorageHealthExecutor,
    build_synthetic_health_check_definitions,
)
from atlas.modules.health_checks.domain.models import HealthCheckDefinition, HealthCheckRunState
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import (
    InventoryDeviceLifecycle,
    InventoryDeviceType,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.hitachi-health"
STORAGE_ID = "836000123456"


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


def definitions() -> tuple[HealthCheckDefinition, ...]:
    controller, capacity, _fabric = build_synthetic_health_check_definitions(
        organization_id="organization.atlas.local",
        environment="development",
        anchor_at=NOW,
    )
    return (
        replace(
            controller,
            connector_id=PACKAGE_ID,
            connector_version="0.1.0",
            target_id="target.hitachi.opscenter.configured",
        ),
        capacity,
    )


def build_executor(
    *,
    configurations: Iterable[object] = (),
    instances: Iterable[object] = (),
    devices: Iterable[object] = (),
    credentials_available: bool = True,
    routes: Mapping[str, SyntheticHitachiResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredHitachiHealthExecutor, SyntheticHitachiTransport]:
    transport = SyntheticHitachiTransport(routes or {})
    executor = ConfiguredHitachiHealthExecutor(
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
        fallback_executor=SyntheticStorageHealthExecutor(),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        runtime_state_repository=runtime_state_repository,
    )
    return executor, transport


@pytest.mark.asyncio
async def test_controller_check_fails_safely_without_one_configured_instance() -> None:
    executor, transport = build_executor()
    controller, _ = definitions()

    result = await executor.execute(controller, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert result.step_count == 0
    assert transport.requests == []
    assert "single active configured Hitachi MCP" in result.partial_reasons[0]


@pytest.mark.asyncio
async def test_controller_check_does_not_contact_disabled_configured_mcp() -> None:
    configuration = SimpleNamespace(
        configuration_id="connection_configuration.hitachi-health",
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        hostname="opscenter.example.internal",
        port=23450,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.hitachi.readonly",
    )
    instance = SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        instance_state=DISABLED_UNCONFIGURED,
    )
    executor, transport = build_executor(
        configurations=(configuration,),
        instances=(instance,),
        runtime_state_repository=InMemoryBundledConnectorRuntimeStateRepository(),
    )
    controller, _ = definitions()

    result = await executor.execute(controller, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "must be enabled" in result.partial_reasons[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_controller_check_uses_configured_read_only_hitachi_transport() -> None:
    configuration = SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        hostname="opscenter.example.internal",
        port=23450,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.hitachi.readonly",
    )
    instance = SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        instance_state=DISABLED_UNCONFIGURED,
    )
    device = SimpleNamespace(
        device_type=InventoryDeviceType.STORAGE,
        vendor="Hitachi Vantara",
        serial_number=STORAGE_ID,
    )
    routes = {
        "/v1/objects/storages": SyntheticHitachiResponse(
            payload={
                "data": [
                    {
                        "storageDeviceId": STORAGE_ID,
                        "model": "VSP G400",
                        "serialNumber": 123456,
                    }
                ]
            }
        ),
        f"/v1/objects/storages/{STORAGE_ID}/components/instance": SyntheticHitachiResponse(
            payload={"ctls": [{"location": "CTL1", "status": "Normal"}]}
        ),
    }
    executor, transport = build_executor(
        configurations=(configuration,),
        instances=(instance,),
        devices=(device,),
        routes=routes,
    )
    controller, _ = definitions()

    result = await executor.execute(controller, started_at=NOW)

    assert result.state is HealthCheckRunState.COMPLETED
    assert transport.requests == [
        "/v1/objects/storages",
        f"/v1/objects/storages/{STORAGE_ID}/components/instance",
    ]
    assert result.observations[0].value == "normal"


@pytest.mark.asyncio
async def test_capacity_uses_configured_read_only_hitachi_transport() -> None:
    configuration = SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        hostname="opscenter.example.internal",
        port=23450,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.hitachi.readonly",
    )
    instance = SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        instance_state=DISABLED_UNCONFIGURED,
    )
    device = SimpleNamespace(
        device_type=InventoryDeviceType.STORAGE,
        vendor="Hitachi Vantara",
        serial_number=STORAGE_ID,
    )
    executor, transport = build_executor(
        configurations=(configuration,),
        instances=(instance,),
        devices=(device,),
        routes={
            "/v1/objects/storages": SyntheticHitachiResponse(
                payload={
                    "data": [
                        {"storageDeviceId": STORAGE_ID, "model": "VSP G400", "serialNumber": 1}
                    ]
                }
            ),
            f"/v1/objects/storages/{STORAGE_ID}/pools": SyntheticHitachiResponse(
                payload={
                    "data": [
                        {
                            "poolId": 5,
                            "poolName": "Production",
                            "usedCapacityRate": 78,
                            "warningThreshold": 75,
                            "depletionThreshold": 90,
                        }
                    ]
                }
            ),
        },
    )
    _, capacity = definitions()

    result = await executor.execute(capacity, started_at=NOW)

    assert result.state is HealthCheckRunState.COMPLETED
    assert result.observations[0].value == "78"
    assert transport.requests == [
        "/v1/objects/storages",
        f"/v1/objects/storages/{STORAGE_ID}/pools",
    ]


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_hitachi() -> None:
    configuration = SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        hostname="opscenter.example.internal",
        port=23450,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.hitachi.readonly",
    )
    instance = SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        instance_state=DISABLED_UNCONFIGURED,
    )
    device = SimpleNamespace(
        device_type=InventoryDeviceType.STORAGE,
        vendor="Hitachi Vantara",
        serial_number=STORAGE_ID,
        lifecycle=InventoryDeviceLifecycle.ACTIVE,
    )
    executor, transport = build_executor(
        configurations=(configuration,),
        instances=(instance,),
        devices=(device,),
        credentials_available=False,
    )
    controller, _ = definitions()

    result = await executor.execute(controller, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "credential reference is unavailable" in result.partial_reasons[0]
    assert transport.requests == []
