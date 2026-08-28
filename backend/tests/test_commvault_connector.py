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
async def test_unrecognized_status_maps_to_unknown() -> None:
    connector, _transport = client(
        {
            JOB_PATH: SyntheticCommvaultResponse(
                payload={
                    "totalRecordsWithoutPaging": 1,
                    "jobs": [_job_summary(104, status="Completed w/ one or more errors")],
                }
            )
        }
    )

    result = await connector.read_job_status()

    assert result.jobs[0].status is CommvaultJobStatus.UNKNOWN


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
