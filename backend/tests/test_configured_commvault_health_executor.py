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
    CommvaultConnectionTestTransportFactory,
    ConnectorAuthorizationHeaderLease,
    ConnectorConnectionTestError,
    ConnectorCredentialMaterializer,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.commvault.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.commvault.ports import CommvaultTransport
from atlas.modules.connectors.vendors.commvault.synthetic import (
    SyntheticCommvaultFault,
    SyntheticCommvaultResponse,
    SyntheticCommvaultTransport,
)
from atlas.modules.health_checks.adapters.configured_commvault import (
    ConfiguredCommvaultHealthExecutor,
)
from atlas.modules.health_checks.adapters.synthetic import (
    SyntheticStorageHealthExecutor,
    build_synthetic_health_check_definitions,
)
from atlas.modules.health_checks.domain.models import HealthCheckDefinition, HealthCheckRunState
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.commvault-health"
JOB_PATH = "/webservice/Job?jobFilter=backup&jobCategory=All&completedJobLookupTime=86400"


def _job_summary(job_id: int, *, status: str) -> dict[str, object]:
    return {
        "jobSummary": {
            "jobId": job_id,
            "status": status,
            "jobType": "Backup",
            "percentComplete": 100 if status == "Completed" else 40,
            "subclientName": "IndexBackup",
            "destClientName": "firewalltestcs",
        }
    }


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
    def __init__(self, transport: SyntheticCommvaultTransport) -> None:
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
    ) -> CommvaultTransport:
        del (
            hostname,
            port,
            trust_profile_id,
            credential_provider,
            timeout_seconds,
            maximum_response_bytes,
        )
        return self.transport


def job_status_definition() -> HealthCheckDefinition:
    (
        _controller,
        _capacity,
        _fabric,
        _huawei_controller,
        _huawei_capacity,
        _pacific_node,
        _pacific_capacity,
        _vcenter_host,
        commvault_job,
    ) = build_synthetic_health_check_definitions(
        organization_id="organization.atlas.local",
        environment="development",
        anchor_at=NOW,
    )
    return replace(
        commvault_job,
        connector_id=PACKAGE_ID,
        connector_version="0.1.0",
        target_id="target.commvault.configured",
    )


def build_executor(
    *,
    configurations: Iterable[object] = (),
    instances: Iterable[object] = (),
    devices: Iterable[object] = (),
    credentials_available: bool = True,
    routes: Mapping[str, SyntheticCommvaultResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredCommvaultHealthExecutor, SyntheticCommvaultTransport]:
    transport = SyntheticCommvaultTransport(dict(routes or {}))
    executor = ConfiguredCommvaultHealthExecutor(
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
            CommvaultConnectionTestTransportFactory, TransportFactory(transport)
        ),
        fallback_executor=SyntheticStorageHealthExecutor(),
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        runtime_state_repository=runtime_state_repository,
    )
    return executor, transport


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        configuration_id="connection_configuration.commvault-health",
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        hostname="commvault.example.internal",
        port=443,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.commvault.readonly",
    )


def _instance() -> SimpleNamespace:
    return SimpleNamespace(
        connector_id=PACKAGE_ID,
        instance_id=INSTANCE_ID,
        instance_state=DISABLED_UNCONFIGURED,
    )


def _device() -> SimpleNamespace:
    return SimpleNamespace(
        device_type=InventoryDeviceType.BACKUP,
        vendor="Commvault",
        serial_number="commvault-cs-01",
        lifecycle=InventoryDeviceLifecycle.ACTIVE,
    )


@pytest.mark.asyncio
async def test_job_check_fails_safely_without_one_configured_instance() -> None:
    executor, transport = build_executor()

    result = await executor.execute(job_status_definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert transport.requests == []
    assert "single active configured Commvault MCP" in result.partial_reasons[0]


@pytest.mark.asyncio
async def test_job_check_does_not_contact_disabled_configured_mcp() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        runtime_state_repository=InMemoryBundledConnectorRuntimeStateRepository(),
    )

    result = await executor.execute(job_status_definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "must be enabled" in result.partial_reasons[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_job_check_reports_normal_for_completed_job() -> None:
    routes = {
        JOB_PATH: SyntheticCommvaultResponse(
            payload={"jobs": [_job_summary(102, status="Completed")]}
        )
    }
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    result = await executor.execute(job_status_definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.COMPLETED
    assert transport.requests == [JOB_PATH]
    assert result.observations[0].value == "Completed"
    assert result.findings == ()


@pytest.mark.asyncio
async def test_job_check_reports_critical_for_killed_job() -> None:
    routes = {
        JOB_PATH: SyntheticCommvaultResponse(payload={"jobs": [_job_summary(103, status="Killed")]})
    }
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    result = await executor.execute(job_status_definition(), started_at=NOW)

    # A finding alone does not make the run PARTIAL -- only an incomplete collection does,
    # matching every prior configured health executor's precedent exactly.
    assert result.state is HealthCheckRunState.COMPLETED
    assert len(result.findings) == 1
    assert transport.requests == [JOB_PATH]


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_commvault() -> None:
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        credentials_available=False,
    )

    result = await executor.execute(job_status_definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "credential reference is unavailable" in result.partial_reasons[0]
    assert transport.requests == []


@pytest.mark.asyncio
async def test_transport_fault_is_reported_safely() -> None:
    routes = {JOB_PATH: SyntheticCommvaultResponse(fault=SyntheticCommvaultFault.UNAVAILABLE)}
    executor, transport = build_executor(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    result = await executor.execute(job_status_definition(), started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert "failed safely" in result.partial_reasons[0]
    assert transport.requests == [JOB_PATH]


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
