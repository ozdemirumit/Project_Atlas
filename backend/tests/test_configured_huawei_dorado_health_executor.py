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
    HuaweiDoradoConnectionTestTransportFactory,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.huawei_dorado.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.huawei_dorado.ports import HuaweiDoradoTransport
from atlas.modules.connectors.vendors.huawei_dorado.synthetic import (
    SyntheticHuaweiDoradoTransport,
    SyntheticHuaweiFault,
    SyntheticHuaweiResponse,
)
from atlas.modules.health_checks.adapters.configured_huawei_dorado import (
    ConfiguredHuaweiDoradoHealthExecutor,
)
from atlas.modules.health_checks.adapters.synthetic import (
    SyntheticStorageHealthExecutor,
    build_synthetic_health_check_definitions,
)
from atlas.modules.health_checks.domain.models import HealthCheckDefinition, HealthCheckRunState
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.huawei-health"
SYSTEM_ID = "2102350ABC"
SYSTEM_PATH = "/system/"
CONTROLLER_PATH = "/controller"
STORAGE_POOL_PATH = "/storagepool"


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
    def __init__(self, transport: SyntheticHuaweiDoradoTransport) -> None:
        self.transport = transport

    def create(
        self,
        *,
        hostname: str,
        port: int,
        system_id: str,
        trust_profile_id: str,
        credential_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> HuaweiDoradoTransport:
        del (
            hostname,
            port,
            system_id,
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
        huawei_controller,
        huawei_capacity,
        _pacific_node,
        _pacific_capacity,
    ) = build_synthetic_health_check_definitions(
        organization_id="organization.atlas.local",
        environment="development",
        anchor_at=NOW,
    )
    return (
        replace(
            huawei_controller,
            connector_id=PACKAGE_ID,
            connector_version="0.1.0",
            target_id="target.huawei.dorado.configured",
        ),
        replace(
            huawei_capacity,
            connector_id=PACKAGE_ID,
            connector_version="0.1.0",
            target_id="target.huawei.dorado.configured",
        ),
    )


def build_executor(
    *,
    configurations: Iterable[object] = (),
    instances: Iterable[object] = (),
    devices: Iterable[object] = (),
    credentials_available: bool = True,
    routes: Mapping[str, SyntheticHuaweiResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredHuaweiDoradoHealthExecutor, SyntheticHuaweiDoradoTransport]:
    transport = SyntheticHuaweiDoradoTransport(routes or {})
    executor = ConfiguredHuaweiDoradoHealthExecutor(
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
            HuaweiDoradoConnectionTestTransportFactory, TransportFactory(transport)
        ),
        fallback_executor=SyntheticStorageHealthExecutor(),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        runtime_state_repository=runtime_state_repository,
    )
    return executor, transport


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        configuration_id="connection_configuration.huawei-health",
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        hostname="dorado.example.internal",
        port=8088,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.huawei.dorado.readonly",
        system_id=SYSTEM_ID,
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
        serial_number=SYSTEM_ID,
        lifecycle=InventoryDeviceLifecycle.ACTIVE,
    )


@pytest.mark.asyncio
async def test_controller_check_fails_safely_without_one_configured_instance() -> None:
    executor, transport = build_executor()
    controller, _capacity = definitions()

    result = await executor.execute(controller, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert transport.requests == []
    assert "single active configured Huawei Dorado MCP" in result.partial_reasons[0]


@pytest.mark.asyncio
async def test_controller_check_does_not_contact_disabled_configured_mcp() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        runtime_state_repository=InMemoryBundledConnectorRuntimeStateRepository(),
    )
    controller, _capacity = definitions()

    result = await executor.execute(controller, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "must be enabled" in result.partial_reasons[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_controller_check_uses_configured_read_only_huawei_transport() -> None:
    routes = {
        CONTROLLER_PATH: SyntheticHuaweiResponse(
            payload={
                "error": {"code": 0},
                "data": [{"ID": "0A", "ROLE": "Primary", "HEALTHSTATUS": "1"}],
            }
        )
    }
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )
    controller, _capacity = definitions()

    result = await executor.execute(controller, started_at=NOW)

    assert result.state is HealthCheckRunState.COMPLETED
    assert transport.requests == [CONTROLLER_PATH]
    assert result.observations[0].value == "normal"


@pytest.mark.asyncio
async def test_capacity_check_computes_utilization_from_raw_capacity() -> None:
    routes = {
        STORAGE_POOL_PATH: SyntheticHuaweiResponse(
            payload={
                "error": {"code": 0},
                "data": [
                    {
                        "NAME": "StoragePool001",
                        "USERTOTALCAPACITY": "1000",
                        "USERFREECAPACITY": "220",
                        "HEALTHSTATUS": "1",
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
    _controller, capacity = definitions()

    result = await executor.execute(capacity, started_at=NOW)

    assert result.state is HealthCheckRunState.COMPLETED
    assert result.observations[0].value == "78.0"
    assert transport.requests == [STORAGE_POOL_PATH]


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_huawei() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        credentials_available=False,
    )
    controller, _capacity = definitions()

    result = await executor.execute(controller, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "credential reference is unavailable" in result.partial_reasons[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_transport_fault_is_reported_safely() -> None:
    routes = {CONTROLLER_PATH: SyntheticHuaweiResponse(fault=SyntheticHuaweiFault.UNAVAILABLE)}
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )
    controller, _capacity = definitions()

    result = await executor.execute(controller, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "failed safely" in result.partial_reasons[0]
    assert transport.requests == [CONTROLLER_PATH]


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
        _huawei_controller,
        _huawei_capacity,
        _pacific_node,
        _pacific_capacity,
    ) = build_synthetic_health_check_definitions(
        organization_id="organization.atlas.local",
        environment="development",
        anchor_at=NOW,
    )

    result = await executor.execute(hitachi_controller, started_at=NOW)

    assert result.state in {HealthCheckRunState.COMPLETED, HealthCheckRunState.PARTIAL}
    assert transport.requests == []
