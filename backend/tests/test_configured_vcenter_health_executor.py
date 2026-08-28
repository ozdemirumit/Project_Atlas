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
    VCenterConnectionTestTransportFactory,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.vcenter.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.vcenter.ports import VCenterTransport
from atlas.modules.connectors.vendors.vcenter.synthetic import (
    SyntheticVCenterFault,
    SyntheticVCenterResponse,
    SyntheticVCenterTransport,
)
from atlas.modules.health_checks.adapters.configured_vcenter import ConfiguredVCenterHealthExecutor
from atlas.modules.health_checks.adapters.synthetic import (
    SyntheticStorageHealthExecutor,
    build_synthetic_health_check_definitions,
)
from atlas.modules.health_checks.domain.models import HealthCheckDefinition, HealthCheckRunState
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.vcenter-health"
HOST_PATH = "/api/vcenter/host"


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


def host_definition() -> HealthCheckDefinition:
    (
        _controller,
        _capacity,
        _fabric,
        _huawei_controller,
        _huawei_capacity,
        _pacific_node,
        _pacific_capacity,
        host,
    ) = build_synthetic_health_check_definitions(
        organization_id="organization.atlas.local",
        environment="development",
        anchor_at=NOW,
    )
    return replace(
        host,
        connector_id=PACKAGE_ID,
        connector_version="0.1.0",
        target_id="target.vcenter.configured",
    )


def build_executor(
    *,
    configurations: Iterable[object] = (),
    instances: Iterable[object] = (),
    devices: Iterable[object] = (),
    credentials_available: bool = True,
    routes: Mapping[str, SyntheticVCenterResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredVCenterHealthExecutor, SyntheticVCenterTransport]:
    transport = SyntheticVCenterTransport(dict(routes or {}))
    executor = ConfiguredVCenterHealthExecutor(
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
        fallback_executor=SyntheticStorageHealthExecutor(),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        runtime_state_repository=runtime_state_repository,
    )
    return executor, transport


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        configuration_id="connection_configuration.vcenter-health",
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


@pytest.mark.asyncio
async def test_host_check_fails_safely_without_one_configured_instance() -> None:
    executor, transport = build_executor()

    result = await executor.execute(host_definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert transport.requests == []
    assert "single active configured vCenter MCP" in result.partial_reasons[0]


@pytest.mark.asyncio
async def test_host_check_does_not_contact_disabled_configured_mcp() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        runtime_state_repository=InMemoryBundledConnectorRuntimeStateRepository(),
    )

    result = await executor.execute(host_definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "must be enabled" in result.partial_reasons[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_host_check_reports_normal_for_connected_powered_on_host() -> None:
    routes = {
        HOST_PATH: SyntheticVCenterResponse(
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
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    result = await executor.execute(host_definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.COMPLETED
    assert transport.requests == [HOST_PATH]
    assert result.observations[0].value == "CONNECTED/POWERED_ON"
    assert result.findings == ()


@pytest.mark.asyncio
async def test_host_check_reports_critical_for_not_responding_host() -> None:
    routes = {
        HOST_PATH: SyntheticVCenterResponse(
            payload=[
                {
                    "host": "host-22",
                    "name": "esxi-02.lab.example",
                    "connection_state": "NOT_RESPONDING",
                    "power_state": "POWERED_ON",
                }
            ]
        )
    }
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    result = await executor.execute(host_definition(), started_at=NOW)

    # A finding alone does not make the run PARTIAL -- only an incomplete collection does,
    # matching the Huawei Dorado/Pacific executors' precedent exactly.
    assert result.state is HealthCheckRunState.COMPLETED
    assert len(result.findings) == 1
    assert transport.requests == [HOST_PATH]


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_vcenter() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        credentials_available=False,
    )

    result = await executor.execute(host_definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "credential reference is unavailable" in result.partial_reasons[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_transport_fault_is_reported_safely() -> None:
    routes = {HOST_PATH: SyntheticVCenterResponse(fault=SyntheticVCenterFault.UNAVAILABLE)}
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    result = await executor.execute(host_definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "failed safely" in result.partial_reasons[0]
    assert transport.requests == [HOST_PATH]


@pytest.mark.asyncio
async def test_other_definitions_are_delegated_to_the_fallback_executor() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
    )
    hitachi_controller, *_rest = build_synthetic_health_check_definitions(
        organization_id="organization.atlas.local",
        environment="development",
        anchor_at=NOW,
    )

    result = await executor.execute(hitachi_controller, started_at=NOW)

    assert result.state in {HealthCheckRunState.COMPLETED, HealthCheckRunState.PARTIAL}
    assert transport.requests == []
