from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.persistence.models import ConnectorPackageAcquisitionModel
from atlas.modules.connectors.adapters.acquisition_archive_filesystem import (
    FileSystemAcquiredPackagePublisher,
)
from atlas.modules.connectors.adapters.acquisition_archive_memory import (
    InMemoryAcquiredPackagePublisher,
)
from atlas.modules.connectors.adapters.acquisition_memory import (
    InMemoryPackageAcquisitionRepository,
)
from atlas.modules.connectors.adapters.acquisition_postgres import (
    PostgreSQLPackageAcquisitionRepository,
)
from atlas.modules.connectors.application.acquisition import (
    ACQUISITION_PROFILE,
    PackageAcquisitionService,
)
from atlas.modules.connectors.application.acquisition_ports import PackageAcquisitionError
from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.mcp_builder.adapters.candidate_archive_memory import (
    InMemoryMcpBuilderCandidateArchivePublisher,
)
from atlas.modules.mcp_builder.adapters.candidate_handoff_memory import (
    InMemoryMcpBuilderCandidateHandoffRepository,
)
from atlas.modules.mcp_builder.application.candidate_archive import (
    DeterministicCandidateArchiveBuilder,
)
from atlas.modules.mcp_builder.application.generator import BuilderGeneratedContent
from atlas.modules.mcp_builder.domain.candidate_handoff import (
    CandidateCapabilityEvidence,
    CandidateHandoffState,
    CandidateSignatureState,
    McpBuilderCandidateHandoff,
)

NOW = datetime(2026, 8, 5, 14, 0, tzinfo=UTC)


class CandidateLineage(TypedDict):
    project_id: str
    project_version: int
    project_digest: str
    source_digest: str
    checkpoint_id: str
    checkpoint_digest: str
    generation_id: str
    generation_digest: str
    artifact_digest: str
    validation_id: str
    validation_digest: str
    domain_review_id: str
    domain_review_digest: str
    domain_reviewed_by: str
    security_review_id: str
    security_review_digest: str
    security_reviewed_by: str
    lab_validation_id: str
    lab_validation_digest: str
    lab_operated_by: str
    organization_id: str
    environment_id: str
    custodied_by: str
    handoff_profile: str
    archive_contract_version: str


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class FailingAuditSink:
    async def record(self, event: AuditRecord) -> None:
        raise RuntimeError("audit unavailable")


def actor(
    subject_id: str = "subject.registry.intake",
    *,
    organization_id: str = "organization.development",
    method: AuthenticationMethod = AuthenticationMethod.LDAP,
    assurance: AssuranceLevel = AssuranceLevel.MULTI_FACTOR,
    kind: SubjectKind = SubjectKind.HUMAN,
) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name="Registry Intake Operator",
        kind=kind,
        provider_id="provider.ldap.test",
        authentication_method=method,
        assurance_level=assurance,
        authenticated_at=NOW,
        organization_id=organization_id,
        role_ids=("role.development.operator",),
    )


def candidate() -> tuple[McpBuilderCandidateHandoff, bytes]:
    lineage: CandidateLineage = {
        "project_id": "mcp-builder-project.test-package",
        "project_version": 1,
        "project_digest": "1" * 64,
        "source_digest": "2" * 64,
        "checkpoint_id": "mcp-builder-design.test-package",
        "checkpoint_digest": "3" * 64,
        "generation_id": "mcp-builder-generation.test-package",
        "generation_digest": "4" * 64,
        "artifact_digest": "5" * 64,
        "validation_id": "mcp-builder-validation.test-package",
        "validation_digest": "6" * 64,
        "domain_review_id": "mcp-builder-domain-review.test-package",
        "domain_review_digest": "7" * 64,
        "domain_reviewed_by": "subject.domain.reviewer",
        "security_review_id": "mcp-builder-security-review.test-package",
        "security_review_digest": "8" * 64,
        "security_reviewed_by": "subject.security.reviewer",
        "lab_validation_id": "mcp-builder-lab-validation.test-package",
        "lab_validation_digest": "9" * 64,
        "lab_operated_by": "subject.lab.operator",
        "organization_id": "organization.development",
        "environment_id": "environment.development",
        "custodied_by": "subject.package.custodian",
        "handoff_profile": "atlas.candidate-handoff.python312.v1",
        "archive_contract_version": "mcp-builder-candidate-zip.v1",
    }
    capability = CandidateCapabilityEvidence(
        candidate_id="capability.storage.health.read",
        capability_class="C1",
        required_permission="storage.health.read",
        supported_product_versions=("Synthetic Storage 1.0",),
        source_citations=("source.openapi.paths.systems.get",),
    )
    envelope = {
        "schema_version": "atlas.mcp-builder-candidate-handoff-envelope.v1",
        **lineage,
        "state": "candidate_quarantined",
        "signature_state": "unsigned",
        "capabilities": [
            {
                "candidate_id": capability.candidate_id,
                "capability_class": capability.capability_class,
                "required_permission": capability.required_permission,
                "supported_product_versions": capability.supported_product_versions,
                "source_citations": capability.source_citations,
            }
        ],
        "network_destinations": ("lab-api.example.invalid:443",),
        "limitations": ("Synthetic evidence only.",),
        "unsupported_behavior": ("No production execution.",),
        "generated_file_count": 1,
        "manual_change_count": 0,
        "package_signed": False,
        "connector_registered": False,
        "connector_installed": False,
        "connector_enabled": False,
        "runtime_trust_granted": False,
        "execution_authorized": False,
        "infrastructure_mutation_performed": False,
    }
    archive = DeterministicCandidateArchiveBuilder().build(
        files=(
            BuilderGeneratedContent(
                relative_path="src/connector.py",
                media_type="text/x-python",
                content="def health():\n    return {'status': 'synthetic'}\n",
            ),
        ),
        envelope=envelope,
    )
    payload = {
        **lineage,
        "state": "candidate_quarantined",
        "package_filename": "mcp-builder-project.test-package.zip",
        "package_digest": archive.digest,
        "package_size_bytes": archive.size_bytes,
        "package_entry_count": archive.entry_count,
        "generated_file_count": 1,
        "generated_size_bytes": len(b"def health():\n    return {'status': 'synthetic'}\n"),
        "envelope_digest": archive.envelope_digest,
        "signature_state": "unsigned",
        "capabilities": [
            {
                "candidate_id": capability.candidate_id,
                "capability_class": capability.capability_class,
                "required_permission": capability.required_permission,
                "supported_product_versions": capability.supported_product_versions,
                "source_citations": capability.source_citations,
            }
        ],
        "network_destinations": ("lab-api.example.invalid:443",),
        "limitations": ("Synthetic evidence only.",),
        "unsupported_behavior": ("No production execution.",),
        "manual_change_count": 0,
    }
    handoff = McpBuilderCandidateHandoff(
        handoff_id="mcp-builder-candidate-handoff.test-package",
        schema_version="atlas.mcp-builder-candidate-handoff.v1",
        version=1,
        state=CandidateHandoffState.CANDIDATE_QUARANTINED,
        **lineage,
        package_filename="mcp-builder-project.test-package.zip",
        package_digest=archive.digest,
        package_size_bytes=archive.size_bytes,
        package_entry_count=archive.entry_count,
        generated_file_count=1,
        generated_size_bytes=len(b"def health():\n    return {'status': 'synthetic'}\n"),
        envelope_digest=archive.envelope_digest,
        signature_state=CandidateSignatureState.UNSIGNED,
        capabilities=(capability,),
        network_destinations=("lab-api.example.invalid:443",),
        limitations=("Synthetic evidence only.",),
        unsupported_behavior=("No production execution.",),
        manual_change_count=0,
        canonical_digest=PackageAcquisitionService._digest(payload),
        request_fingerprint="a" * 64,
        idempotency_key="candidate-test-001",
        created_at=NOW,
    )
    return handoff, archive.content


async def service_fixture(
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
) -> tuple[
    PackageAcquisitionService,
    McpBuilderCandidateHandoff,
    bytes,
    InMemoryPackageAcquisitionRepository,
    InMemoryMcpBuilderCandidateHandoffRepository,
    InMemoryMcpBuilderCandidateArchivePublisher,
    InMemoryAcquiredPackagePublisher,
]:
    handoff, content = candidate()
    handoffs = InMemoryMcpBuilderCandidateHandoffRepository()
    source_archives = InMemoryMcpBuilderCandidateArchivePublisher()
    acquisitions = InMemoryPackageAcquisitionRepository()
    publisher = InMemoryAcquiredPackagePublisher()
    assert await handoffs.add(handoff)
    assert await source_archives.publish(package_digest=handoff.package_digest, content=content)
    service = PackageAcquisitionService(
        repository=acquisitions,
        handoff_source=handoffs,
        archive_source=source_archives,
        publisher=publisher,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id="environment.development",
        clock=lambda: NOW,
    )
    return service, handoff, content, acquisitions, handoffs, source_archives, publisher


async def acquire(
    service: PackageAcquisitionService,
    handoff: McpBuilderCandidateHandoff,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "acquisition-test-001",
) -> ConnectorPackageAcquisition:
    return await service.create(
        actor=subject or actor(),
        source_handoff_id=handoff.handoff_id,
        source_handoff_digest=handoff.canonical_digest,
        package_digest=handoff.package_digest,
        acquisition_profile=ACQUISITION_PROFILE,
        acknowledged_unsigned_unattested_quarantine=True,
        idempotency_key=key,
        correlation_id="cor_package_acquisition_test",
    )


@pytest.mark.asyncio
async def test_acquires_exact_candidate_bytes_idempotently_without_authority() -> None:
    audit = CollectingAuditSink()
    service, handoff, content, _, _, _, _ = await service_fixture(audit)

    first = await acquire(service, handoff)
    second = await acquire(service, handoff)
    copied = await service.read_acquired_archive(actor=actor(), acquisition_id=first.acquisition_id)

    assert copied == content
    assert second == replace(first, reused=True)
    assert first.state.value == "quarantined"
    assert first.signature_state.value == "unsigned"
    assert first.attestation_state.value == "unattested"
    assert first.publisher_identity == "unattested.generated"
    assert first.package_digest == handoff.package_digest
    assert not first.registry_validation_completed
    assert not first.connector_registered
    assert not first.execution_authorized
    assert not first.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == [
        "connector_package_acquired_quarantined"
    ]


@pytest.mark.asyncio
async def test_concurrent_replay_produces_one_receipt_and_one_audit() -> None:
    audit = CollectingAuditSink()
    service, handoff, _, repository, _, _, _ = await service_fixture(audit)

    first, second = await asyncio.gather(acquire(service, handoff), acquire(service, handoff))

    assert first.acquisition_id == second.acquisition_id
    assert {first.reused, second.reused} == {False, True}
    assert await repository.get_by_handoff(source_handoff_id=handoff.handoff_id) is not None
    assert len(audit.records) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subject",
    [
        actor("subject.package.custodian"),
        actor("subject.domain.reviewer"),
        actor("subject.security.reviewer"),
        actor("subject.lab.operator"),
        actor(method=AuthenticationMethod.DEVELOPMENT, assurance=AssuranceLevel.DEVELOPMENT),
        actor(kind=SubjectKind.SERVICE),
    ],
)
async def test_rejects_non_independent_or_non_enterprise_actor(
    subject: AuthenticatedSubject,
) -> None:
    service, handoff, _, _, _, _, _ = await service_fixture()

    with pytest.raises(PackageAcquisitionError):
        await acquire(service, handoff, subject=subject)


@pytest.mark.asyncio
async def test_rejects_tampered_handoff_and_mismatched_request() -> None:
    service, handoff, _, _, handoffs, _, _ = await service_fixture()
    handoffs._records[handoff.handoff_id] = replace(handoff, canonical_digest="b" * 64)

    with pytest.raises(PackageAcquisitionError) as caught:
        await acquire(service, handoff)

    assert caught.value.code == "package_acquisition_source_integrity_failed"


@pytest.mark.asyncio
async def test_audit_failure_does_not_create_receipt() -> None:
    service, handoff, _, repository, _, _, _ = await service_fixture(FailingAuditSink())

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await acquire(service, handoff)

    assert await repository.get_by_handoff(source_handoff_id=handoff.handoff_id) is None


@pytest.mark.asyncio
async def test_wrong_scope_and_unacknowledged_requests_fail_closed() -> None:
    service, handoff, _, _, _, _, _ = await service_fixture()

    with pytest.raises(PackageAcquisitionError) as scope_error:
        await acquire(service, handoff, subject=actor(organization_id="organization.other"))
    assert scope_error.value.code == "package_acquisition_not_found"

    with pytest.raises(PackageAcquisitionError) as acknowledgement_error:
        await service.create(
            actor=actor(),
            source_handoff_id=handoff.handoff_id,
            source_handoff_digest=handoff.canonical_digest,
            package_digest=handoff.package_digest,
            acquisition_profile=ACQUISITION_PROFILE,
            acknowledged_unsigned_unattested_quarantine=False,
            idempotency_key="acquisition-test-002",
            correlation_id="cor_package_acquisition_test",
        )
    assert acknowledgement_error.value.code == "package_acquisition_acknowledgement_required"


@pytest.mark.asyncio
async def test_filesystem_publisher_is_immutable_and_detects_corruption(tmp_path: Path) -> None:
    handoff, content = candidate()
    publisher = FileSystemAcquiredPackagePublisher(root=tmp_path / "quarantine")

    assert await publisher.publish(package_digest=handoff.package_digest, content=content)
    assert not await publisher.publish(package_digest=handoff.package_digest, content=content)
    assert (
        await publisher.read(
            package_digest=handoff.package_digest, size_bytes=handoff.package_size_bytes
        )
        == content
    )
    path = tmp_path / "quarantine" / handoff.package_digest[:2] / f"{handoff.package_digest}.zip"
    path.write_bytes(b"changed")
    with pytest.raises(PackageAcquisitionError) as caught:
        await publisher.read(
            package_digest=handoff.package_digest, size_bytes=handoff.package_size_bytes
        )
    assert caught.value.code == "package_acquisition_archive_integrity_failed"


@pytest.mark.asyncio
async def test_postgres_mapping_preserves_the_immutable_receipt() -> None:
    service, handoff, _, _, _, _, _ = await service_fixture()
    acquisition = await acquire(service, handoff)
    row = ConnectorPackageAcquisitionModel(
        **PostgreSQLPackageAcquisitionRepository._values(acquisition)
    )

    assert PostgreSQLPackageAcquisitionRepository._to_domain(row) == acquisition


def test_package_acquisition_api_requires_csrf_and_returns_safe_receipt(tmp_path: Path) -> None:
    service, handoff, _, _, _, _, _ = asyncio.run(service_fixture())
    intake = actor()
    provider = BasicTestIdentityProvider(intake)
    app_settings = settings(
        development_subject_id=intake.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-acquisition-request.v1",
        "source_handoff_id": handoff.handoff_id,
        "source_handoff_digest": handoff.canonical_digest,
        "package_digest": handoff.package_digest,
        "acquisition_profile": ACQUISITION_PROFILE,
        "acknowledged_unsigned_unattested_quarantine": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=provider,
            package_acquisition_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-acquisitions"
        denied = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "package-acquisition-api-001"},
        )
        stale = client.post(
            endpoint,
            json={**payload, "source_handoff_digest": "0" * 64},
            headers={
                "Idempotency-Key": "package-acquisition-api-stale",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "package-acquisition-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        acquisition_id = created.json()["data"]["acquisition_id"]
        read = client.get(f"{endpoint}/{acquisition_id}")

    assert denied.status_code == 403
    assert stale.status_code == 409
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert read.json()["data"]["canonical_digest"] == data["canonical_digest"]
    assert data["state"] == "quarantined"
    assert data["signature_state"] == "unsigned"
    assert data["attestation_state"] == "unattested"
    assert data["integrity_verified"] is True
    for field in (
        "package_signed",
        "publisher_attested",
        "registry_validation_completed",
        "connector_registered",
        "connector_approved",
        "connector_installed",
        "connector_enabled",
        "target_configured",
        "credentials_resolved",
        "runtime_trust_granted",
        "execution_authorized",
        "deployment_approved",
        "infrastructure_mutation_performed",
    ):
        assert data[field] is False
