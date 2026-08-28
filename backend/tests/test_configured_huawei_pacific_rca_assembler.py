from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
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
from atlas.modules.rca.adapters.configured_huawei_pacific import (
    ConfiguredHuaweiPacificRcaAssembler,
    _identity,
)
from atlas.modules.rca.domain.models import (
    ConfirmationLevel,
    RcaCase,
    RcaCaseState,
    RcaCreateRequest,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.huawei-pacific-rca"
CLUSTER_SERVERS_PATH = "/api/v2/cluster/servers"
TARGET_ID = f"asset.storage.{_identity('node1', 'node2')}"


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


def build_assembler(
    *,
    configurations: Iterable[object] = (),
    instances: Iterable[object] = (),
    devices: Iterable[object] = (),
    credentials_available: bool = True,
    routes: Mapping[str, SyntheticHuaweiPacificResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredHuaweiPacificRcaAssembler, SyntheticHuaweiPacificTransport]:
    transport = SyntheticHuaweiPacificTransport(routes or {})
    assembler = ConfiguredHuaweiPacificRcaAssembler(
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
    return assembler, transport


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        configuration_id="connection_configuration.huawei-pacific-rca",
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


def _node(node_id: str, *, running_status: str) -> dict[str, object]:
    return {
        "id": node_id,
        "name": f"node-{node_id}",
        "management_ip": "192.0.2.10",
        "model": "Pacific 9550",
        "running_status": running_status,
        "in_cluster": True,
    }


def _request(target_id: str = TARGET_ID) -> RcaCreateRequest:
    return RcaCreateRequest(
        incident_id="INC-2026-0299",
        target_id=target_id,
        user_report="Storage finding appeared during the service window.",
        expected_behavior="Cluster nodes remain online and redundant.",
        actual_behavior="A node reports a non-online running status.",
        window_start=NOW - timedelta(hours=24),
        window_end=NOW,
        max_evidence_records=12,
    )


async def _build(
    assembler: ConfiguredHuaweiPacificRcaAssembler, target_id: str = TARGET_ID
) -> RcaCase:
    return await assembler.build(
        _request(target_id),
        requested_by="subject.development.operator",
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        site_id="site.local",
        created_at=NOW,
        version=1,
        prior_version_id=None,
    )


@pytest.mark.asyncio
async def test_build_raises_without_one_configured_instance() -> None:
    assembler, transport = build_assembler()

    with pytest.raises(KeyError):
        await _build(assembler)

    assert transport.requests == []


@pytest.mark.asyncio
async def test_build_raises_when_configured_mcp_disabled() -> None:
    assembler, transport = build_assembler(
        configurations=(_configuration(),),
        instances=(_instance(),),
        runtime_state_repository=InMemoryBundledConnectorRuntimeStateRepository(),
    )

    with pytest.raises(KeyError):
        await _build(assembler)

    assert transport.requests == []


@pytest.mark.asyncio
async def test_build_raises_without_allowlisted_cluster() -> None:
    assembler, transport = build_assembler(
        configurations=(_configuration(),),
        instances=(_instance(),),
    )

    with pytest.raises(KeyError):
        await _build(assembler)

    assert transport.requests == []


@pytest.mark.asyncio
async def test_build_raises_for_a_target_id_not_matching_the_read_cluster() -> None:
    routes = {
        CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(
            payload={"result": {"code": 0}, "data": [_node("node1", running_status="online")]}
        ),
    }
    assembler, transport = build_assembler(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    with pytest.raises(KeyError):
        await _build(assembler, target_id="asset.storage.lab.other")

    assert transport.requests == [CLUSTER_SERVERS_PATH]


@pytest.mark.asyncio
async def test_build_returns_active_finding_case_from_real_cluster_read() -> None:
    routes = {
        CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(
            payload={
                "result": {"code": 0},
                "data": [
                    _node("node1", running_status="online"),
                    _node("node2", running_status="offline"),
                ],
            }
        ),
    }
    assembler, transport = build_assembler(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    case = await _build(assembler)

    assert case.state is RcaCaseState.PROVISIONAL
    assert case.target_id == TARGET_ID
    assert case.data_profile == "configured_huawei_pacific_read_only"
    assert len(case.hypotheses) == 2
    assert [item.rank for item in case.hypotheses] == [1, 2]
    assert case.hypotheses[0].confirmation_level is ConfirmationLevel.SUPPORTED
    assert "node:node2" in case.hypotheses[0].statement
    evidence_ids = {item.evidence_id for item in case.evidence}
    referenced = {
        reference
        for hypothesis in case.hypotheses
        for reference in (*hypothesis.supporting_evidence, *hypothesis.contradicting_evidence)
    }
    assert referenced <= evidence_ids
    assert case.root_cause_confirmed is False
    assert transport.requests == [CLUSTER_SERVERS_PATH]


@pytest.mark.asyncio
async def test_build_returns_no_active_finding_case_when_all_nodes_are_online() -> None:
    routes = {
        CLUSTER_SERVERS_PATH: SyntheticHuaweiPacificResponse(
            payload={
                "result": {"code": 0},
                "data": [
                    _node("node1", running_status="online"),
                    _node("node2", running_status="online"),
                ],
            }
        ),
    }
    assembler, _transport = build_assembler(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    case = await _build(assembler)

    assert case.state is RcaCaseState.INCONCLUSIVE
    assert case.hypotheses == ()
    assert case.findings == ()
    assert case.provisional_statement.confirmation_level is ConfirmationLevel.INCONCLUSIVE
    assert case.root_cause_confirmed is False


@pytest.mark.asyncio
async def test_missing_credential_reference_raises_without_contacting_huawei() -> None:
    assembler, transport = build_assembler(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        credentials_available=False,
    )

    with pytest.raises(KeyError):
        await _build(assembler)

    assert transport.requests == []
