from __future__ import annotations

import asyncio
import io
import json
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink, actor, candidate

from atlas.api.app import create_app
from atlas.core.persistence.models import ConnectorPackageValidationModel
from atlas.modules.connectors.adapters.acquisition_archive_memory import (
    InMemoryAcquiredPackagePublisher,
)
from atlas.modules.connectors.adapters.acquisition_memory import (
    InMemoryPackageAcquisitionRepository,
)
from atlas.modules.connectors.adapters.validation_intake_memory import (
    InMemoryPackageValidationRepository,
)
from atlas.modules.connectors.adapters.validation_intake_postgres import (
    PostgreSQLPackageValidationRepository,
)
from atlas.modules.connectors.application.acquisition import (
    ACQUISITION_LIMITATIONS,
    ACQUISITION_PROFILE,
    ACQUISITION_SCHEMA,
    PUBLISHER_IDENTITY,
    PackageAcquisitionService,
)
from atlas.modules.connectors.application.validation_intake import (
    JSON_SCHEMA_DRAFT,
    VALIDATION_PROFILE,
    PackageValidationService,
)
from atlas.modules.connectors.application.validation_intake_ports import (
    PackageValidationError,
)
from atlas.modules.connectors.domain.acquisition import (
    AcquiredCapabilityEvidence,
    ConnectorPackageAcquisition,
    PackageAcquisitionSource,
    PackageAcquisitionState,
    PackageSignatureState,
    PublisherAttestationState,
)
from atlas.modules.connectors.domain.validation_intake import (
    ConnectorPackageValidation,
    PackageValidationOutcome,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.mcp_builder.application.candidate_archive import (
    DeterministicCandidateArchiveBuilder,
)
from atlas.modules.mcp_builder.application.generator import BuilderGeneratedContent


def validator(
    subject_id: str = "subject.package.validator",
    *,
    organization_id: str = "organization.development",
    method: AuthenticationMethod = AuthenticationMethod.LDAP,
    assurance: AssuranceLevel = AssuranceLevel.MULTI_FACTOR,
    kind: SubjectKind = SubjectKind.HUMAN,
) -> AuthenticatedSubject:
    return actor(
        subject_id,
        organization_id=organization_id,
        method=method,
        assurance=assurance,
        kind=kind,
    )


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def package_files(
    *,
    invalid_manifest: bool = False,
    overrides: dict[str, str] | None = None,
    additions: dict[str, str] | None = None,
) -> tuple[BuilderGeneratedContent, ...]:
    capability_id = "capability.storage.health.read"
    manifest = {
        "schema_version": "atlas.connector-manifest.v1",
        "connector_id": "connector.synthetic-storage",
        "version": "0.1.0-draft",
        "status": "quarantined_generated_draft",
        "sdk_profile": "atlas.python312.v1",
        "target_products": ["Synthetic Storage"],
        "network_destinations": ["lab-api.example.invalid:443"],
        "configuration_keys": ["endpoint"],
        "secret_reference_ids": ["credential_ref"],
        "capabilities": [
            {
                "id": capability_id,
                "class": "C1",
                "permission": "storage.health.read",
                "handler_status": "draft_fail_closed",
            }
        ],
        "runtime_trust": invalid_manifest,
        "execution_authorized": False,
    }
    config_schema = {
        "$schema": JSON_SCHEMA_DRAFT,
        "$id": "atlas://generated/config.schema.json",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "endpoint": {"type": "string", "x-atlas-sensitive": False},
            "credential_ref": {
                "type": "string",
                "format": "atlas-secret-reference",
                "x-atlas-secret-value": False,
            },
        },
        "required": ["credential_ref", "endpoint"],
    }
    input_schema = {
        "$schema": JSON_SCHEMA_DRAFT,
        "$id": f"atlas://generated/{capability_id}/input.schema.json",
        "type": "object",
        "additionalProperties": False,
        "properties": {},
        "x-atlas-parameter-evidence-count": 0,
        "x-atlas-generation-status": "draft_requires_schema_review",
    }
    output_schema = {
        "$schema": JSON_SCHEMA_DRAFT,
        "$id": f"atlas://generated/{capability_id}/output.schema.json",
        "type": "object",
        "additionalProperties": True,
        "x-atlas-response-code-evidence": ["200"],
        "x-atlas-generation-status": "draft_requires_schema_review",
    }
    contents = {
        "atlas-connector.yaml": canonical_json(manifest),
        "schemas/config/config.schema.json": canonical_json(config_schema),
        "schemas/inputs/capability_read.schema.json": canonical_json(input_schema),
        "schemas/outputs/capability_read.schema.json": canonical_json(output_schema),
        "pyproject.toml": (
            "[build-system]\n"
            'requires = ["setuptools>=75,<76"]\n'
            'build-backend = "setuptools.build_meta"\n\n'
            "[project]\n"
            'name = "atlas-generated-0123456789ab"\n'
            'version = "0.1.0.dev0"\n'
            'description = "Quarantined Project Atlas connector review scaffold"\n'
            'requires-python = ">=3.12,<3.13"\n'
            "dependencies = []\n\n"
            "[tool.ruff]\n"
            'target-version = "py312"\n'
            "line-length = 100\n\n"
            "[tool.mypy]\n"
            'python_version = "3.12"\n'
            "strict = true\n\n"
            "[tool.pytest.ini_options]\n"
            'testpaths = ["tests"]\n'
        ),
        "README.md": "# Quarantined connector review scaffold\n",
        "src/atlas_generated_connector/__init__.py": '"""Quarantined draft."""\n',
        "src/atlas_generated_connector/errors.py": "class DraftError(RuntimeError):\n    pass\n",
        "src/atlas_generated_connector/capabilities/__init__.py": (
            '"""Generated capability drafts."""\n'
        ),
        "src/atlas_generated_connector/capabilities/capability_read.py": (
            "def draft_handler() -> None:\n    raise RuntimeError('draft only')\n"
        ),
        "tests/contract/test_capability_read.py": "def test_draft() -> None:\n    assert True\n",
        "tests/fixtures/capability_read.json": canonical_json({"synthetic": True}),
    }
    contents.update(overrides or {})
    contents.update(additions or {})
    return tuple(
        BuilderGeneratedContent(
            relative_path=path,
            media_type="application/json" if path.endswith((".json", ".yaml")) else "text/plain",
            content=value,
        )
        for path, value in sorted(contents.items())
    )


def acquisition_payload(acquisition: ConnectorPackageAcquisition) -> dict[str, object]:
    return {
        "state": acquisition.state.value,
        "source_type": acquisition.source_type.value,
        "source_handoff_id": acquisition.source_handoff_id,
        "source_handoff_digest": acquisition.source_handoff_digest,
        "source_project_id": acquisition.source_project_id,
        "source_custodied_by": acquisition.source_custodied_by,
        "source_domain_reviewed_by": acquisition.source_domain_reviewed_by,
        "source_security_reviewed_by": acquisition.source_security_reviewed_by,
        "source_lab_operated_by": acquisition.source_lab_operated_by,
        "organization_id": acquisition.organization_id,
        "environment_id": acquisition.environment_id,
        "acquired_by": acquisition.acquired_by,
        "acquisition_profile": acquisition.acquisition_profile,
        "archive_contract_version": acquisition.archive_contract_version,
        "package_filename": acquisition.package_filename,
        "package_digest": acquisition.package_digest,
        "package_size_bytes": acquisition.package_size_bytes,
        "publisher_identity": acquisition.publisher_identity,
        "signature_state": acquisition.signature_state.value,
        "attestation_state": acquisition.attestation_state.value,
        "capabilities": PackageAcquisitionService._capability_payload(acquisition.capabilities),
        "limitations": acquisition.limitations,
    }


async def service_fixture(
    *,
    invalid_manifest: bool = False,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
    overrides: dict[str, str] | None = None,
    additions: dict[str, str] | None = None,
) -> tuple[
    PackageValidationService,
    ConnectorPackageAcquisition,
    InMemoryPackageValidationRepository,
    InMemoryAcquiredPackagePublisher,
]:
    handoff, original_content = candidate()
    with zipfile.ZipFile(io.BytesIO(original_content), "r") as source:
        envelope: dict[str, Any] = json.loads(source.read("ATLAS-CANDIDATE-HANDOFF.json"))
    files = package_files(
        invalid_manifest=invalid_manifest, overrides=overrides, additions=additions
    )
    envelope["generated_file_count"] = len(files)
    archive = DeterministicCandidateArchiveBuilder().build(files=files, envelope=envelope)
    capability = AcquiredCapabilityEvidence(
        capability_id="capability.storage.health.read",
        capability_class="C1",
        required_permission="storage.health.read",
        supported_product_versions=("Synthetic Storage 1.0",),
    )
    draft = ConnectorPackageAcquisition(
        acquisition_id="connector-package-acquisition.validation-test",
        schema_version=ACQUISITION_SCHEMA,
        version=1,
        state=PackageAcquisitionState.QUARANTINED,
        source_type=PackageAcquisitionSource.MCP_BUILDER_HANDOFF,
        source_handoff_id=handoff.handoff_id,
        source_handoff_digest=handoff.canonical_digest,
        source_project_id=handoff.project_id,
        source_custodied_by=handoff.custodied_by,
        source_domain_reviewed_by=handoff.domain_reviewed_by,
        source_security_reviewed_by=handoff.security_reviewed_by,
        source_lab_operated_by=handoff.lab_operated_by,
        organization_id=handoff.organization_id,
        environment_id=handoff.environment_id,
        acquired_by="subject.registry.intake",
        acquisition_profile=ACQUISITION_PROFILE,
        archive_contract_version=handoff.archive_contract_version,
        package_filename=handoff.package_filename,
        package_digest=archive.digest,
        package_size_bytes=archive.size_bytes,
        publisher_identity=PUBLISHER_IDENTITY,
        signature_state=PackageSignatureState.UNSIGNED,
        attestation_state=PublisherAttestationState.UNATTESTED,
        capabilities=(capability,),
        limitations=ACQUISITION_LIMITATIONS,
        canonical_digest="0" * 64,
        request_fingerprint="1" * 64,
        idempotency_key="acquisition-validation-test-001",
        acquired_at=handoff.created_at,
    )
    acquisition = replace(
        draft, canonical_digest=PackageAcquisitionService._digest(acquisition_payload(draft))
    )
    acquisitions = InMemoryPackageAcquisitionRepository()
    archives = InMemoryAcquiredPackagePublisher()
    validations = InMemoryPackageValidationRepository()
    assert await acquisitions.add(acquisition)
    assert await archives.publish(package_digest=archive.digest, content=archive.content)
    service = PackageValidationService(
        repository=validations,
        acquisition_source=acquisitions,
        archive_source=archives,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id="environment.development",
        clock=lambda: handoff.created_at,
    )
    return service, acquisition, validations, archives


async def validate(
    service: PackageValidationService,
    acquisition: ConnectorPackageAcquisition,
    *,
    subject: AuthenticatedSubject | None = None,
    key: str = "package-validation-test-001",
) -> ConnectorPackageValidation:
    return await service.create(
        actor=subject or validator(),
        source_acquisition_id=acquisition.acquisition_id,
        source_acquisition_digest=acquisition.canonical_digest,
        package_digest=acquisition.package_digest,
        validation_profile=VALIDATION_PROFILE,
        acknowledged_untrusted_quarantined_package=True,
        idempotency_key=key,
        correlation_id="cor_package_validation_test",
    )


@pytest.mark.asyncio
async def test_validates_manifest_and_schemas_idempotently_without_authority() -> None:
    audit = CollectingAuditSink()
    service, acquisition, _, _ = await service_fixture(audit_sink=audit)

    first = await validate(service, acquisition)
    second = await validate(service, acquisition)

    assert first.outcome is PackageValidationOutcome.PASSED
    assert all(item.state.value == "passed" for item in first.checks)
    assert len(first.schema_evidence) == 3
    assert second == replace(first, reused=True)
    assert not first.dependency_scan_completed
    assert not first.connector_registered
    assert not first.runtime_trust_granted
    assert not first.execution_authorized
    assert not first.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == [
        "connector_package_manifest_schema_passed"
    ]


@pytest.mark.asyncio
async def test_invalid_manifest_creates_a_failed_bounded_report() -> None:
    service, acquisition, repository, _ = await service_fixture(invalid_manifest=True)

    report = await validate(service, acquisition)

    assert report.outcome is PackageValidationOutcome.FAILED
    assert report.checks[2].state.value == "failed"
    assert report.checks[3].state.value == "passed"
    assert (
        await repository.get_by_acquisition(source_acquisition_id=acquisition.acquisition_id)
        == report
    )


@pytest.mark.asyncio
async def test_archive_corruption_fails_without_creating_a_report() -> None:
    service, acquisition, repository, archives = await service_fixture()
    archives._archives[acquisition.package_digest] = b"changed"

    with pytest.raises(PackageValidationError) as caught:
        await validate(service, acquisition)

    assert caught.value.code == "package_validation_archive_integrity_failed"
    assert (
        await repository.get_by_acquisition(source_acquisition_id=acquisition.acquisition_id)
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subject",
    [
        validator("subject.registry.intake"),
        validator("subject.package.custodian"),
        validator("subject.domain.reviewer"),
        validator("subject.security.reviewer"),
        validator("subject.lab.operator"),
        validator(method=AuthenticationMethod.DEVELOPMENT, assurance=AssuranceLevel.DEVELOPMENT),
        validator(kind=SubjectKind.SERVICE),
    ],
)
async def test_rejects_non_independent_or_non_enterprise_validator(
    subject: AuthenticatedSubject,
) -> None:
    service, acquisition, _, _ = await service_fixture()

    with pytest.raises(PackageValidationError):
        await validate(service, acquisition, subject=subject)


@pytest.mark.asyncio
async def test_audit_failure_does_not_create_validation_report() -> None:
    service, acquisition, repository, _ = await service_fixture(audit_sink=FailingAuditSink())

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await validate(service, acquisition)

    assert (
        await repository.get_by_acquisition(source_acquisition_id=acquisition.acquisition_id)
        is None
    )


@pytest.mark.asyncio
async def test_concurrent_validation_produces_one_report() -> None:
    service, acquisition, repository, _ = await service_fixture()

    first, second = await asyncio.gather(
        validate(service, acquisition), validate(service, acquisition)
    )

    assert first.validation_id == second.validation_id
    assert {first.reused, second.reused} == {False, True}
    assert len(repository._records) == 1


@pytest.mark.asyncio
async def test_postgres_mapping_preserves_the_validation_report() -> None:
    service, acquisition, _, _ = await service_fixture()
    report = await validate(service, acquisition)
    row = ConnectorPackageValidationModel(**PostgreSQLPackageValidationRepository._values(report))

    assert PostgreSQLPackageValidationRepository._to_domain(row) == report


def test_package_validation_api_requires_csrf_and_returns_safe_report(tmp_path: Path) -> None:
    service, acquisition, _, _ = asyncio.run(service_fixture())
    subject = validator()
    provider = BasicTestIdentityProvider(subject)
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-validation-request.v1",
        "source_acquisition_id": acquisition.acquisition_id,
        "source_acquisition_digest": acquisition.canonical_digest,
        "package_digest": acquisition.package_digest,
        "validation_profile": VALIDATION_PROFILE,
        "acknowledged_untrusted_quarantined_package": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=provider,
            package_validation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-validations"
        denied = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "package-validation-api-001"},
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "package-validation-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        validation_id = created.json()["data"]["validation_id"]
        read = client.get(f"{endpoint}/{validation_id}")

    assert denied.status_code == 403
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["outcome"] == "passed"
    assert len(data["schema_evidence"]) == 3
    assert read.json()["data"]["canonical_digest"] == data["canonical_digest"]
    for field in (
        "dependency_scan_completed",
        "vulnerability_scan_completed",
        "malware_scan_completed",
        "connector_registered",
        "connector_installed",
        "runtime_trust_granted",
        "execution_authorized",
        "infrastructure_mutation_performed",
    ):
        assert data[field] is False
