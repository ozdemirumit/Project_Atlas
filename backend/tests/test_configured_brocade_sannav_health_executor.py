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
    SyntheticBrocadeFault,
    SyntheticBrocadeResponse,
    SyntheticBrocadeSanNavTransport,
)
from atlas.modules.health_checks.adapters.configured_brocade_sannav import (
    ConfiguredBrocadeSanNavHealthExecutor,
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

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.brocade-health"
FABRIC_WWN = "10:00:00:05:1e:35:1a:00"
FABRICS_PATH = "/external-api/v1/discovery/fabrics/"
FABRIC_MEMBERS_PATH = f"/external-api/v1/discovery/fabric-members/?principalSwitchWWN={FABRIC_WWN}"
FAULT_EVENTS_PATH = "/external-api/v2/fault/events/"


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


def definition() -> HealthCheckDefinition:
    (
        controller,
        capacity,
        fabric,
        huawei_controller,
        huawei_capacity,
        pacific_node,
        pacific_capacity,
        vcenter_host,
        commvault_job,
    ) = build_synthetic_health_check_definitions(
        organization_id="organization.atlas.local",
        environment="development",
        anchor_at=NOW,
    )
    del (
        controller,
        capacity,
        huawei_controller,
        huawei_capacity,
        pacific_node,
        pacific_capacity,
        vcenter_host,
        commvault_job,
    )
    return replace(
        fabric,
        connector_id=PACKAGE_ID,
        connector_version="0.1.0",
        target_id="target.brocade.sannav.configured",
    )


def build_executor(
    *,
    configurations: Iterable[object] = (),
    instances: Iterable[object] = (),
    devices: Iterable[object] = (),
    credentials_available: bool = True,
    routes: Mapping[str, SyntheticBrocadeResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredBrocadeSanNavHealthExecutor, SyntheticBrocadeSanNavTransport]:
    transport = SyntheticBrocadeSanNavTransport(routes or {})
    executor = ConfiguredBrocadeSanNavHealthExecutor(
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
        fallback_executor=SyntheticStorageHealthExecutor(),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        runtime_state_repository=runtime_state_repository,
    )
    return executor, transport


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        configuration_id="connection_configuration.brocade-health",
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
async def test_fabric_check_fails_safely_without_one_configured_instance() -> None:
    executor, transport = build_executor()

    result = await executor.execute(definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert result.step_count == 0
    assert transport.requests == []
    assert "single active configured Brocade SANnav MCP" in result.partial_reasons[0]


@pytest.mark.asyncio
async def test_fabric_check_does_not_contact_disabled_configured_mcp() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        runtime_state_repository=InMemoryBundledConnectorRuntimeStateRepository(),
    )

    result = await executor.execute(definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "must be enabled" in result.partial_reasons[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_fabric_check_uses_configured_read_only_brocade_transport_with_no_faults() -> None:
    routes = {
        FABRICS_PATH: SyntheticBrocadeResponse(
            payload={"Fabrics": [{"principalSwitchWwn": FABRIC_WWN, "name": "Fabric-A"}]}
        ),
        FABRIC_MEMBERS_PATH: SyntheticBrocadeResponse(payload={"Switches": []}),
        FAULT_EVENTS_PATH: SyntheticBrocadeResponse(payload={"events": []}),
    }
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    result = await executor.execute(definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.COMPLETED
    assert transport.requests == [FABRICS_PATH, FABRIC_MEMBERS_PATH, FAULT_EVENTS_PATH]
    assert result.observations[0].value == "0"
    assert result.findings == ()


@pytest.mark.asyncio
async def test_fabric_check_reports_warning_never_critical_for_nonzero_faults() -> None:
    routes = {
        FABRICS_PATH: SyntheticBrocadeResponse(
            payload={"Fabrics": [{"principalSwitchWwn": FABRIC_WWN, "name": "Fabric-A"}]}
        ),
        FABRIC_MEMBERS_PATH: SyntheticBrocadeResponse(payload={"Switches": []}),
        FAULT_EVENTS_PATH: SyntheticBrocadeResponse(payload={"events": [{}, {}]}),
    }
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    result = await executor.execute(definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.PARTIAL
    assert result.observations[0].value == "2"
    assert len(result.findings) == 1
    assert result.findings[0].severity.value == "warning"
    assert transport.requests == [FABRICS_PATH, FABRIC_MEMBERS_PATH, FAULT_EVENTS_PATH]


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_brocade() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        credentials_available=False,
    )

    result = await executor.execute(definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "credential reference is unavailable" in result.partial_reasons[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_transport_fault_is_reported_safely() -> None:
    routes = {
        FABRICS_PATH: SyntheticBrocadeResponse(fault=SyntheticBrocadeFault.UNAVAILABLE),
    }
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    result = await executor.execute(definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "failed safely" in result.partial_reasons[0]
    assert transport.requests == [FABRICS_PATH]


@pytest.mark.asyncio
async def test_other_definitions_are_delegated_to_the_fallback_executor() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
    )
    (
        controller,
        _capacity,
        _fabric,
        _huawei_controller,
        _huawei_capacity,
        _pacific_node,
        _pacific_capacity,
        _vcenter_host,
        _commvault_job,
    ) = build_synthetic_health_check_definitions(
        organization_id="organization.atlas.local",
        environment="development",
        anchor_at=NOW,
    )

    result = await executor.execute(controller, started_at=NOW)

    assert result.state in {HealthCheckRunState.COMPLETED, HealthCheckRunState.PARTIAL}
    assert transport.requests == []
