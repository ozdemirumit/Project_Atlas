from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.adapters.memory import InMemoryConnectorRegistryRepository
from atlas.modules.connectors.application.registry import (
    PACKAGE_REGISTER,
    ConnectorAccessContext,
    ConnectorRegistryService,
    FoundationConnectorValidator,
)
from atlas.modules.connectors.domain.models import (
    ConnectorHealth,
    ConnectorInstance,
    InstanceLifecycle,
    PackageLifecycle,
    SideEffect,
)
from atlas.modules.connectors.vendors.commvault.client import (
    CommvaultClient,
    CommvaultConnectorError,
)
from atlas.modules.connectors.vendors.commvault.domain import CommvaultJobStatus
from atlas.modules.connectors.vendors.commvault.manifest import (
    JOB_STATUS_CAPABILITY_ID,
    build_candidate_manifest,
)
from atlas.modules.connectors.vendors.commvault.synthetic import (
    SyntheticCommvaultFault,
    SyntheticCommvaultResponse,
    SyntheticCommvaultTransport,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.commvault.lab"
JOB_PATH = "/webservice/Job?jobFilter=backup&jobCategory=All&completedJobLookupTime=86400"
CLIENT_PATH = "/webservice/Client"
STORAGE_POLICY_PATH = "/webservice/V2/StoragePolicy"
STORAGE_POLICY_DETAIL_PATH = "/webservice/V2/StoragePolicy/2?propertyLevel=10"
SUBCLIENT_PATH = "/webservice/Subclient?clientId=2"
SUBCLIENT_BROWSE_PATH = "/webservice/Subclient/2/Browse?path=%5C"


def _job_summary(
    job_id: int, *, status: str, client_name: str = "firewalltestcs"
) -> dict[str, object]:
    return {
        "jobSummary": {
            "jobId": job_id,
            "status": status,
            "jobType": "Backup",
            "percentComplete": 100 if status == "Completed" else 40,
            "subclientName": "IndexBackup",
            "destClientName": client_name,
        }
    }


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def access_context() -> ConnectorAccessContext:
    return ConnectorAccessContext(
        subject_id="subject.test.backup-engineer",
        actor_type="human",
        authentication_method="development",
        assurance_level="development",
        organization_id="organization.test",
        environment_id="environment.lab",
        site_id="site.backup-lab",
        target_id="target.commvault.lab",
        correlation_id="cor_commvault_candidate",
        permissions=frozenset({PACKAGE_REGISTER}),
    )


def connector_instance() -> ConnectorInstance:
    return ConnectorInstance(
        instance_id=INSTANCE_ID,
        package_id="connector.commvault.commserve",
        package_version="0.1.0",
        organization_id="organization.test",
        environment_id="environment.lab",
        site_id="site.backup-lab",
        target_id="target.commvault.lab",
        enabled_capability_ids=frozenset({JOB_STATUS_CAPABILITY_ID}),
        secret_reference_ids=("secret.commvault.read-only",),
        lifecycle=InstanceLifecycle.DISABLED,
        health=ConnectorHealth.UNKNOWN,
        configuration_revision=1,
        created_at=NOW,
        created_by="subject.test.backup-engineer",
    )


def client(
    routes: dict[str, SyntheticCommvaultResponse], **limits: int
) -> tuple[CommvaultClient, SyntheticCommvaultTransport]:
    transport = SyntheticCommvaultTransport(routes)
    return CommvaultClient(transport=transport, clock=lambda: NOW, **limits), transport


@pytest.mark.asyncio
async def test_candidate_manifest_is_c1_and_remains_quarantined() -> None:
    package_manifest = build_candidate_manifest(
        digest_sha256="a" * 64,
        network_destination="commvault.lab.example:443",
    )
    assert package_manifest.generated is True
    assert {capability.capability_class for capability in package_manifest.capabilities} == {
        CapabilityClass.C1_READ_ONLY
    }
    assert {
        effect for capability in package_manifest.capabilities for effect in capability.side_effects
    } == {SideEffect.READ}

    repository = InMemoryConnectorRegistryRepository()
    service = ConnectorRegistryService(
        repository=repository,
        audit_sink=CollectingAuditSink(),
        validator=FoundationConnectorValidator(clock=lambda: NOW),
        clock=lambda: NOW,
    )
    package = await service.register_package(package_manifest, access_context())

    assert package.lifecycle is PackageLifecycle.QUARANTINED
    with pytest.raises(ValueError, match="approved host and port"):
        build_candidate_manifest(
            digest_sha256="b" * 64,
            network_destination="commvault.lab.example:443/path",
        )


@pytest.mark.asyncio
async def test_job_status_reads_real_fields() -> None:
    connector, transport = client(
        {
            JOB_PATH: SyntheticCommvaultResponse(
                payload={
                    "totalRecordsWithoutPaging": 2,
                    "jobs": [
                        _job_summary(102, status="Completed"),
                        _job_summary(103, status="Killed", client_name="dr-client"),
                    ],
                }
            )
        }
    )

    result = await connector.read_job_status()

    assert [job.job_id for job in result.jobs] == [102, 103]
    assert result.jobs[0].status is CommvaultJobStatus.COMPLETED
    assert result.jobs[1].status is CommvaultJobStatus.KILLED
    assert result.jobs[1].client_name == "dr-client"
    assert result.evidence_references[0].startswith("commvault://Job#sha256:")
    assert transport.requests == [JOB_PATH]


@pytest.mark.asyncio
async def test_client_inventory_reads_real_fields() -> None:
    connector, transport = client(
        {
            CLIENT_PATH: SyntheticCommvaultResponse(
                payload={
                    "clientProperties": [
                        {
                            "clientProps": {"IsDeletedClient": False},
                            "client": {
                                "osInfo": {"Type": "Windows", "SubType": "Server", "osId": 210},
                                "clientEntity": {
                                    "hostName": "example.test.com",
                                    "clientId": 2,
                                    "clientName": "exampleclient",
                                    "displayName": "ExampleClient",
                                },
                            },
                        },
                        {
                            "clientProps": {"IsDeletedClient": True},
                            "client": {
                                "osInfo": {"Type": "Linux", "SubType": "Server", "osId": 211},
                                "clientEntity": {
                                    "hostName": "old.test.com",
                                    "clientId": 3,
                                    "clientName": "oldclient",
                                    "displayName": "OldClient",
                                },
                            },
                        },
                    ]
                }
            )
        }
    )

    result = await connector.read_client_inventory()

    assert [item.client_id for item in result.clients] == ["2", "3"]
    assert result.clients[0].client_name == "exampleclient"
    assert result.clients[0].os_type == "Windows"
    assert result.clients[0].is_deleted is False
    assert result.clients[1].is_deleted is True
    assert result.evidence_references[0].startswith("commvault://Client#sha256:")
    assert transport.requests == [CLIENT_PATH]


@pytest.mark.asyncio
async def test_client_inventory_tolerates_the_minimal_confirmed_list_shape() -> None:
    """The official REST API reference's own literal example response for the list endpoint
    carries a bare `<clientProps enableAccessControl="false"/>` with no `IsDeletedClient`, and
    no `osInfo` at all -- this is the real minimal shape the connector must not reject."""

    connector, _transport = client(
        {
            CLIENT_PATH: SyntheticCommvaultResponse(
                payload={
                    "clientProperties": [
                        {
                            "clientProps": {"enableAccessControl": False},
                            "client": {
                                "clientEntity": {
                                    "hostName": "client001.company.com",
                                    "clientId": 2,
                                    "clientName": "client001",
                                },
                            },
                        },
                    ]
                }
            )
        }
    )

    result = await connector.read_client_inventory()

    assert result.clients[0].client_id == "2"
    assert result.clients[0].os_type is None
    assert result.clients[0].is_deleted is None


@pytest.mark.asyncio
async def test_storage_policies_read_real_fields() -> None:
    """`numberOfCopies` is not part of this list endpoint's documented response (its literal
    example response carries only `numberOfStreams` alongside the nested `storagePolicy`
    identity), so the list read leaves `number_of_copies` unset (None) -- it is sourced
    separately via `read_storage_policy_copy_count()`."""

    connector, transport = client(
        {
            STORAGE_POLICY_PATH: SyntheticCommvaultResponse(
                payload={
                    "policies": [
                        {
                            "type": 2,
                            "numberOfStreams": 1,
                            "storagePolicy": {
                                "storagePolicyName": "CommServeDR",
                                "storagePolicyId": 2,
                            },
                        }
                    ],
                    "error": {"errorMessage": "", "errorCode": 0},
                }
            )
        }
    )

    result = await connector.read_storage_policies()

    assert result.policies[0].policy_id == "2"
    assert result.policies[0].policy_name == "CommServeDR"
    assert result.policies[0].number_of_copies is None
    assert result.policies[0].number_of_streams == 1
    assert transport.requests == [STORAGE_POLICY_PATH]


@pytest.mark.asyncio
async def test_storage_policy_copy_count_reads_the_details_endpoint() -> None:
    connector, transport = client(
        {
            STORAGE_POLICY_DETAIL_PATH: SyntheticCommvaultResponse(
                payload={
                    "policies": {
                        "numberOfStreams": 50,
                        "numberOfCopies": 5,
                        "auxCopyAlertGB": 0,
                    },
                    "error": {"errorMessage": "", "errorCode": 0},
                }
            )
        }
    )

    count = await connector.read_storage_policy_copy_count("2")

    assert count == 5
    assert transport.requests == [STORAGE_POLICY_DETAIL_PATH]


@pytest.mark.asyncio
async def test_storage_policy_copy_count_rejects_an_unsafe_policy_identifier() -> None:
    connector, transport = client({})

    with pytest.raises(CommvaultConnectorError) as error:
        await connector.read_storage_policy_copy_count("2?propertyLevel=1")

    assert error.value.code == "invalid_target_identifier"
    assert transport.requests == []


@pytest.mark.asyncio
async def test_subclients_read_real_fields() -> None:
    connector, transport = client(
        {
            SUBCLIENT_PATH: SyntheticCommvaultResponse(
                payload={
                    "subClientProperties": [
                        {
                            "subClientEntity": {
                                "subclientId": 2,
                                "subclientName": "default",
                                "clientId": 2,
                                "clientName": "client001",
                                "appName": "File System",
                                "backupsetId": 1,
                                "backupsetName": "defaultBackupSet",
                            }
                        },
                        {
                            "subClientEntity": {
                                "subclientId": 3,
                                "subclientName": "System State",
                                "clientId": 2,
                                "clientName": "client001",
                                "appName": "File System",
                            }
                        },
                    ]
                }
            )
        }
    )

    result = await connector.read_subclients("2")

    assert [item.subclient_id for item in result.subclients] == ["2", "3"]
    assert result.subclients[0].subclient_name == "default"
    assert result.subclients[0].app_name == "File System"
    assert result.evidence_references[0].startswith("commvault://Subclient?clientId=2#sha256:")
    assert transport.requests == [SUBCLIENT_PATH]


@pytest.mark.asyncio
async def test_subclients_rejects_an_unsafe_client_identifier() -> None:
    connector, transport = client({})

    with pytest.raises(CommvaultConnectorError) as error:
        await connector.read_subclients("2?clientId=1")

    assert error.value.code == "invalid_target_identifier"
    assert transport.requests == []


def _browse_response(*, with_items: bool) -> dict[str, object]:
    data_result_set: list[dict[str, object]] | dict[str, object]
    if with_items:
        data_result_set = [
            {
                "name": "|2|#12!C:",
                "path": "\\C:",
                "displayPath": "\\C:",
                "modificationTime": 1409307311,
                "displayName": "C:",
                "size": 107004030976,
                "advancedData": {
                    "archiveGroupId": 3,
                    "referenceTime": 1409341069,
                    "archiveFileId": 11,
                    "backupJobId": 45,
                    "backupTime": 1409341069,
                },
            }
        ]
    else:
        data_result_set = []
    return {
        "browseResponses": [
            {
                "respType": 0,
                "workerId": 19,
                "browseResult": {"queryId": 0, "dataResultSet": data_result_set},
                "session": {"sessionId": "1409670021-19"},
            },
            {
                "respType": 0,
                "workerId": 19,
                "browseResult": {"queryId": 1, "aggrResultSet": {"result": 1 if with_items else 0}},
                "session": {"sessionId": "1409670021-19"},
            },
        ]
    }


@pytest.mark.asyncio
async def test_subclient_browse_reads_real_fields_and_skips_the_aggregate_only_response() -> None:
    connector, transport = client(
        {
            SUBCLIENT_BROWSE_PATH: SyntheticCommvaultResponse(
                payload=_browse_response(with_items=True)
            )
        }
    )

    result = await connector.read_subclient_browse("2")

    assert result.subclient_id == "2"
    assert len(result.items) == 1
    item = result.items[0]
    assert item.name == "|2|#12!C:"
    assert item.path == "\\C:"
    assert item.size == 107004030976
    assert item.modification_time == 1409307311
    assert item.backup_job_id == 45
    assert item.backup_time == 1409341069
    assert item.archive_file_id == 11
    assert transport.requests == [SUBCLIENT_BROWSE_PATH]


@pytest.mark.asyncio
async def test_subclient_browse_tolerates_a_single_item_collapsed_to_an_object() -> None:
    """A real, documented ambiguity: `browseResponses` and `dataResultSet` may each collapse from
    a list to a single object when there is exactly one entry -- both must be tolerated."""

    connector, transport = client(
        {
            SUBCLIENT_BROWSE_PATH: SyntheticCommvaultResponse(
                payload={
                    "browseResponses": {
                        "respType": 0,
                        "workerId": 19,
                        "browseResult": {
                            "queryId": 0,
                            "dataResultSet": {
                                "name": "sample.xml",
                                "path": "\\test_data\\sample.xml",
                            },
                        },
                    }
                }
            )
        }
    )

    result = await connector.read_subclient_browse("2")

    assert len(result.items) == 1
    assert result.items[0].name == "sample.xml"
    assert result.items[0].size is None
    assert transport.requests == [SUBCLIENT_BROWSE_PATH]


@pytest.mark.asyncio
async def test_subclient_browse_with_no_items_returns_an_empty_result() -> None:
    connector, _transport = client(
        {
            SUBCLIENT_BROWSE_PATH: SyntheticCommvaultResponse(
                payload=_browse_response(with_items=False)
            )
        }
    )

    result = await connector.read_subclient_browse("2")

    assert result.items == ()


@pytest.mark.asyncio
async def test_subclient_browse_rejects_an_unsafe_subclient_identifier() -> None:
    connector, transport = client({})

    with pytest.raises(CommvaultConnectorError) as error:
        await connector.read_subclient_browse("2/Browse")

    assert error.value.code == "invalid_target_identifier"
    assert transport.requests == []


@pytest.mark.asyncio
async def test_unrecognized_status_maps_to_unknown() -> None:
    connector, _transport = client(
        {
            JOB_PATH: SyntheticCommvaultResponse(
                payload={
                    "totalRecordsWithoutPaging": 1,
                    "jobs": [_job_summary(104, status="Not A Real Commvault Status")],
                }
            )
        }
    )

    result = await connector.read_job_status()

    assert result.jobs[0].status is CommvaultJobStatus.UNKNOWN


@pytest.mark.asyncio
async def test_the_full_confirmed_status_vocabulary_is_recognized() -> None:
    """All 19 values are drawn from the official REST API reference's own "Valid values are"
    table for `jobSummary.status` -- confirmed by inspecting each entry's page coordinates to
    correctly resolve wrapped multi-word entries (e.g. "Running" and "Running (cannot be
    verified)" are two distinct documented values, not a wrapped duplicate)."""

    raw_statuses = [
        "Running",
        "Waiting",
        "Pending",
        "Suspend",
        "Suspended",
        "Kill Pending",
        "Interrupt Pending",
        "Interrupted",
        "Queued",
        "Running (cannot be verified)",
        "Abnormal Terminated",
        "Cleanup",
        "Completed",
        "Completed w/ one or more errors",
        "Completed w/ one or more warnings",
        "Committed",
        "Failed",
        "Failed to Start",
        "Killed",
    ]
    connector, _transport = client(
        {
            JOB_PATH: SyntheticCommvaultResponse(
                payload={
                    "jobs": [
                        _job_summary(100 + index, status=status)
                        for index, status in enumerate(raw_statuses)
                    ]
                }
            )
        }
    )

    result = await connector.read_job_status()

    assert [job.status for job in result.jobs] == list(CommvaultJobStatus)[:-1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fault", "code", "retryable"),
    [
        (SyntheticCommvaultFault.DENIED, "vendor_permission_denied", False),
        (SyntheticCommvaultFault.TIMEOUT, "target_timeout", True),
        (SyntheticCommvaultFault.THROTTLED, "vendor_rate_limited", True),
        (SyntheticCommvaultFault.UNAVAILABLE, "target_unavailable", True),
    ],
)
async def test_transport_faults_are_mapped_safely(
    fault: SyntheticCommvaultFault, code: str, retryable: bool
) -> None:
    connector, _transport = client({JOB_PATH: SyntheticCommvaultResponse(fault=fault)})

    with pytest.raises(CommvaultConnectorError) as error:
        await connector.read_job_status()

    assert error.value.code == code
    assert error.value.retryable is retryable


@pytest.mark.asyncio
async def test_malformed_and_oversized_responses_are_rejected() -> None:
    malformed, _ = client({JOB_PATH: SyntheticCommvaultResponse(payload={"jobs": "invalid"})})
    oversized, _ = client(
        {
            JOB_PATH: SyntheticCommvaultResponse(
                payload={
                    "jobs": [
                        _job_summary(1, status="Completed"),
                        _job_summary(2, status="Completed"),
                    ]
                }
            )
        },
        maximum_jobs=1,
    )
    oversized_bytes, _ = client(
        {JOB_PATH: SyntheticCommvaultResponse(payload={"jobs": [], "padding": "x" * 128})},
        maximum_response_bytes=64,
    )

    with pytest.raises(CommvaultConnectorError) as malformed_error:
        await malformed.read_job_status()
    with pytest.raises(CommvaultConnectorError) as oversized_error:
        await oversized.read_job_status()
    with pytest.raises(CommvaultConnectorError) as oversized_bytes_error:
        await oversized_bytes.read_job_status()

    assert malformed_error.value.code == "malformed_vendor_response"
    assert oversized_error.value.code == "vendor_response_limit_exceeded"
    assert oversized_bytes_error.value.code == "vendor_response_limit_exceeded"


@pytest.mark.asyncio
async def test_self_test_uses_job_status_and_detects_incompatible_instance() -> None:
    compatible_transport = SyntheticCommvaultTransport(
        {JOB_PATH: SyntheticCommvaultResponse(payload={"jobs": []})}
    )
    unavailable_transport = SyntheticCommvaultTransport({})

    compatible = await CommvaultClient(transport=compatible_transport, clock=lambda: NOW).self_test(
        connector_instance()
    )
    mismatched = await CommvaultClient(
        transport=unavailable_transport, clock=lambda: NOW
    ).self_test(replace(connector_instance(), package_id="connector.other"))

    assert compatible.health is ConnectorHealth.HEALTHY
    assert compatible_transport.requests == [JOB_PATH]
    assert mismatched.health is ConnectorHealth.INCOMPATIBLE
    assert mismatched.code == "connector_instance_package_mismatch"
    assert unavailable_transport.requests == []


def test_synthetic_transport_has_no_external_or_secret_access() -> None:
    transport = SyntheticCommvaultTransport(
        {JOB_PATH: SyntheticCommvaultResponse(payload={"jobs": []})}
    )

    assert transport.network_access is False
    assert transport.secret_access is False


def test_candidate_package_assets_are_strict_and_synthetic_only() -> None:
    package_root = Path(__file__).parents[2] / "mcp" / "connectors" / "commvault"
    schema = json.loads((package_root / "configuration.schema.json").read_text(encoding="utf-8"))
    provenance = json.loads((package_root / "source-provenance.json").read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert "credential_reference_id" in schema["required"]
    assert "password" not in schema["properties"]
    assert "username" not in schema["properties"]
    assert provenance["data_policy"] == "synthetic-only"
    assert provenance["production_credentials_present"] is False
    assert {source["method"] for source in provenance["capability_sources"]} == {"GET"}
