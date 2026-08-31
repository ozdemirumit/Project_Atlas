from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from atlas.modules.backup_operations.adapters.configured_commvault import (
    ConfiguredCommvaultBackupOverviewProvider,
)
from atlas.modules.backup_operations.domain.models import InvestigationState
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
    SyntheticCommvaultResponse,
    SyntheticCommvaultTransport,
)
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.commvault-backup"
CLIENT_PATH = "/webservice/Client"
STORAGE_POLICY_PATH = "/webservice/V2/StoragePolicy"


def _detail_path(policy_id: str) -> str:
    return f"/webservice/V2/StoragePolicy/{policy_id}?propertyLevel=10"


def _subclient_path(client_id: str) -> str:
    return f"/webservice/Subclient?clientId={client_id}"


def _browse_path(subclient_id: str) -> str:
    return f"/webservice/Subclient/{subclient_id}/Browse?path=%5C"


def _subclient_response(client_id: int, subclient_id: int) -> SyntheticCommvaultResponse:
    return SyntheticCommvaultResponse(
        payload={
            "subClientProperties": [
                {
                    "subClientEntity": {
                        "subclientId": subclient_id,
                        "subclientName": "default",
                        "clientId": client_id,
                        "appName": "File System",
                    }
                }
            ]
        }
    )


def _browse_response(*, name: str = "sample.xml") -> SyntheticCommvaultResponse:
    return SyntheticCommvaultResponse(
        payload={
            "browseResponses": [
                {
                    "browseResult": {
                        "queryId": 0,
                        "dataResultSet": [
                            {
                                "name": name,
                                "path": f"\\test_data\\{name}",
                                "size": 2048,
                                "modificationTime": 1409307311,
                                "advancedData": {"backupJobId": 45, "backupTime": 1409341069},
                            }
                        ],
                    }
                },
                {"browseResult": {"queryId": 1, "aggrResultSet": {"result": 1}}},
            ]
        }
    )


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


def build_provider(
    *,
    configurations: Iterable[object] = (),
    instances: Iterable[object] = (),
    devices: Iterable[object] = (),
    credentials_available: bool = True,
    routes: Mapping[str, SyntheticCommvaultResponse] | None = None,
    runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
) -> tuple[ConfiguredCommvaultBackupOverviewProvider, SyntheticCommvaultTransport]:
    transport = SyntheticCommvaultTransport(dict(routes or {}))
    provider = ConfiguredCommvaultBackupOverviewProvider(
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
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        runtime_state_repository=runtime_state_repository,
    )
    return provider, transport


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        configuration_id="connection_configuration.commvault-backup",
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


def _client_item(client_id: int, *, name: str, is_deleted: bool) -> dict[str, object]:
    return {
        "clientProps": {"IsDeletedClient": is_deleted},
        "client": {
            "osInfo": {"Type": "Windows", "SubType": "Server", "osId": 210},
            "clientEntity": {
                "hostName": f"{name}.lab.example",
                "clientId": client_id,
                "clientName": name,
                "displayName": name,
            },
        },
    }


def _routes() -> dict[str, SyntheticCommvaultResponse]:
    return {
        CLIENT_PATH: SyntheticCommvaultResponse(
            payload={
                "clientProperties": [
                    _client_item(1, name="app-server-01", is_deleted=False),
                    _client_item(2, name="app-server-02", is_deleted=True),
                ]
            }
        ),
        STORAGE_POLICY_PATH: SyntheticCommvaultResponse(
            payload={
                "policies": [
                    {
                        "numberOfStreams": 1,
                        "storagePolicy": {
                            "storagePolicyName": "Primary-Policy",
                            "storagePolicyId": 1,
                        },
                    },
                    {
                        "numberOfStreams": 1,
                        "storagePolicy": {
                            "storagePolicyName": "Legacy-Policy",
                            "storagePolicyId": 2,
                        },
                    },
                ]
            }
        ),
        _detail_path("1"): SyntheticCommvaultResponse(
            payload={"policies": {"numberOfStreams": 1, "numberOfCopies": 2}}
        ),
        _detail_path("2"): SyntheticCommvaultResponse(
            payload={"policies": {"numberOfStreams": 1, "numberOfCopies": 0}}
        ),
        _subclient_path("1"): _subclient_response(1, 10),
        _subclient_path("2"): _subclient_response(2, 20),
        _browse_path("10"): _browse_response(name="app-server-01-file.xml"),
        _browse_path("20"): _browse_response(name="app-server-02-file.xml"),
    }


@pytest.mark.asyncio
async def test_overview_reports_unavailable_without_one_configured_instance() -> None:
    provider, transport = build_provider()

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.clients == ()
    assert overview.investigation.state is InvestigationState.INCONCLUSIVE
    assert "single active configured Commvault MCP" in overview.investigation.summary
    assert transport.requests == []


@pytest.mark.asyncio
async def test_overview_reports_unavailable_when_configured_mcp_disabled() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        runtime_state_repository=InMemoryBundledConnectorRuntimeStateRepository(),
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.clients == ()
    assert "must be enabled" in overview.investigation.summary
    assert transport.requests == []


@pytest.mark.asyncio
async def test_overview_reports_unavailable_without_allowlisted_commvault() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.clients == ()
    assert "No active Commvault CommServe" in overview.investigation.summary
    assert transport.requests == []


@pytest.mark.asyncio
async def test_overview_maps_real_clients_and_policies_with_findings() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=_routes(),
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.data_profile == "configured_commvault_read_only"
    assert len(overview.clients) == 2
    assert len(overview.policies) == 2
    assert len(overview.findings) == 2
    deleted_finding = next(f for f in overview.findings if "app-server-02" in f.summary)
    zero_copy_finding = next(f for f in overview.findings if "Legacy-Policy" in f.summary)
    assert deleted_finding.severity.value == "warning"
    assert zero_copy_finding.severity.value == "warning"
    evidence_ids = {item.reference for item in overview.evidence}
    referenced = {
        reference for client in overview.clients for reference in client.evidence_references
    } | {reference for policy in overview.policies for reference in policy.evidence_references}
    assert referenced <= evidence_ids
    assert transport.requests == [
        CLIENT_PATH,
        STORAGE_POLICY_PATH,
        _detail_path("1"),
        _detail_path("2"),
        _subclient_path("1"),
        _browse_path("10"),
        _subclient_path("2"),
        _browse_path("20"),
    ]
    policy_by_id = {policy.policy_id: policy for policy in overview.policies}
    assert policy_by_id["1"].number_of_copies == 2
    assert policy_by_id["2"].number_of_copies == 0
    assert len(overview.recovery_points) == 2
    recovery_point_names = {point.name for point in overview.recovery_points}
    assert recovery_point_names == {"app-server-01-file.xml", "app-server-02-file.xml"}
    point = next(p for p in overview.recovery_points if p.name == "app-server-01-file.xml")
    assert point.client_id == "1"
    assert point.subclient_id == "10"
    assert point.size == 2048
    assert point.backup_job_id == 45
    assert point.modification_time is not None
    assert point.backup_time is not None
    recovery_point_evidence = {
        reference for rp in overview.recovery_points for reference in rp.evidence_references
    }
    assert recovery_point_evidence <= evidence_ids


@pytest.mark.asyncio
async def test_overview_reports_no_findings_when_all_clients_and_policies_are_healthy() -> None:
    routes = {
        CLIENT_PATH: SyntheticCommvaultResponse(
            payload={"clientProperties": [_client_item(1, name="app-server-01", is_deleted=False)]}
        ),
        STORAGE_POLICY_PATH: SyntheticCommvaultResponse(
            payload={
                "policies": [
                    {
                        "numberOfStreams": 1,
                        "storagePolicy": {
                            "storagePolicyName": "Primary-Policy",
                            "storagePolicyId": 1,
                        },
                    }
                ]
            }
        ),
        _detail_path("1"): SyntheticCommvaultResponse(
            payload={"policies": {"numberOfStreams": 1, "numberOfCopies": 2}}
        ),
    }
    provider, _transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.findings == ()


@pytest.mark.asyncio
async def test_overview_degrades_copy_count_gracefully_when_detail_route_is_missing() -> None:
    routes = {
        CLIENT_PATH: SyntheticCommvaultResponse(
            payload={"clientProperties": [_client_item(1, name="app-server-01", is_deleted=False)]}
        ),
        STORAGE_POLICY_PATH: SyntheticCommvaultResponse(
            payload={
                "policies": [
                    {
                        "numberOfStreams": 1,
                        "storagePolicy": {
                            "storagePolicyName": "Primary-Policy",
                            "storagePolicyId": 1,
                        },
                    }
                ]
            }
        ),
        # No _detail_path("1") route configured: the enrichment read fails safely.
    }
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        routes=routes,
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.policies[0].number_of_copies is None
    assert overview.findings == ()
    assert any(
        "Copy-count detail could not be read" in item for item in overview.investigation.unknowns
    )
    assert any(
        "Subclient discovery could not be read" in item for item in overview.investigation.unknowns
    )
    assert overview.recovery_points == ()
    assert transport.requests == [
        CLIENT_PATH,
        STORAGE_POLICY_PATH,
        _detail_path("1"),
        _subclient_path("1"),
    ]


@pytest.mark.asyncio
async def test_missing_credential_reference_does_not_contact_commvault() -> None:
    provider, transport = build_provider(
        configurations=(_configuration(),),
        instances=(_instance(),),
        devices=(_device(),),
        credentials_available=False,
    )

    overview = await provider.get_overview(requested_at=NOW)

    assert overview.clients == ()
    assert "credential reference is unavailable" in overview.investigation.summary
    assert transport.requests == []
