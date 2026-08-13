from __future__ import annotations

import asyncio
import io
import zipfile
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_final_validation import final_operator
from test_registry_publication import (
    publication_fixture,
    publish_package,
)

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.modules.connectors.adapters.package_registration_inspector import (
    BoundedConnectorPackageManifestInspector,
)
from atlas.modules.connectors.adapters.package_registration_memory import (
    InMemoryPackageRegistrationPolicySource,
    InMemoryPackageRegistrationRepository,
)
from atlas.modules.connectors.adapters.package_registration_postgres import (
    PostgreSQLPackageRegistrationRepository,
)
from atlas.modules.connectors.adapters.registry_publication_memory import (
    InMemoryNonProductionRegistryPublisher,
)
from atlas.modules.connectors.application.package_registration import (
    PackageRegistrationService,
    build_development_package_registration_policy,
)
from atlas.modules.connectors.application.package_registration_ports import PackageRegistrationError
from atlas.modules.connectors.application.registry_publication import RegistryPublicationService
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationPolicySnapshot,
    ConnectorPackageRegistrationRecord,
)
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationReceipt,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


class FailSecondAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, record: AuditRecord) -> None:
        self.records.append(record)
        if len(self.records) == 2:
            raise RuntimeError("completion audit unavailable")


def registration_operator(
    subject_id: str = "subject.package-independent-registrar",
) -> AuthenticatedSubject:
    return final_operator(subject_id)


async def registration_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | FailSecondAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    PackageRegistrationService,
    RegistryPublicationService,
    ConnectorInternalRegistryPublicationReceipt,
    ConnectorPackageRegistrationPolicySnapshot,
    InMemoryNonProductionRegistryPublisher,
]:
    publication_service, publication_policy, publisher, _ = await publication_fixture()
    publication = await publish_package(publication_service, publication_policy)
    policy = build_development_package_registration_policy(
        organization_id=publication.organization_id,
        environment_id=publication.environment_id,
        issued_at=publication.published_at - timedelta(hours=1),
        expires_at=publication.published_at + timedelta(days=2),
    )
    if required_assurance_level is not policy.required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        payload = asdict(policy)
        payload.pop("canonical_digest")
        policy = replace(
            policy,
            canonical_digest=PackageRegistrationService._digest(
                PackageRegistrationService._normalize(payload)
            ),
        )
    service = PackageRegistrationService(
        repository=InMemoryPackageRegistrationRepository(),
        publication_source=publication_service,
        policy_source=InMemoryPackageRegistrationPolicySource((policy,)),
        artifact_reader=publisher,
        manifest_inspector=BoundedConnectorPackageManifestInspector(),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=publication.environment_id,
        clock=lambda: publication.published_at,
    )
    return service, publication_service, publication, policy, publisher


async def register_package(
    service: PackageRegistrationService,
    publication: ConnectorInternalRegistryPublicationReceipt,
    policy: ConnectorPackageRegistrationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "package-registration-001",
) -> ConnectorPackageRegistrationRecord:
    return await service.create(
        actor=actor or registration_operator(),
        source_publication_receipt_id=publication.receipt_id,
        source_publication_receipt_digest=publication.canonical_digest,
        package_digest=publication.package_digest,
        registration_policy_id=policy.policy_id,
        registration_policy_digest=policy.canonical_digest,
        purpose="Register this exact published package without installation or runtime authority.",
        acknowledged_registration_grants_no_installation_or_runtime_authority=True,
        idempotency_key=key,
        correlation_id="cor_package_registration",
    )


@pytest.mark.asyncio
async def test_registration_grants_only_installation_governance_eligibility() -> None:
    audit = CollectingAuditSink()
    service, _, publication, policy, publisher = await registration_fixture(audit_sink=audit)

    record = await register_package(service, publication, policy)
    repeated = await register_package(service, publication, policy)

    assert record.package_published and record.connector_registered
    assert record.eligible_for_installation_governance and not record.promotion_blocked
    assert repeated.reused and repeated.record_id == record.record_id
    assert publisher.read_invocation_count == 1
    assert record.manifest.connector_id == publication.connector_id
    assert record.manifest.release_version == publication.release_version
    assert len(record.manifest.capabilities) == 1
    assert not record.connector_installed and not record.instance_created
    assert not record.connector_enabled and not record.target_configured
    assert not record.credentials_resolved and not record.runtime_trust_granted
    assert not record.execution_authorized and not record.deployment_approved
    assert not record.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == [
        "connector_package_registration_requested",
        "connector_package_registration_completed",
    ]


@pytest.mark.asyncio
async def test_registration_optional_step_up_policy_and_human_boundary() -> None:
    service, _, publication, policy, _ = await registration_fixture()
    development_actor = replace(
        registration_operator(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    record = await register_package(service, publication, policy, actor=development_actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.registered_by == development_actor.subject_id

    hardware_service, _, hardware_publication, hardware_policy, _ = await registration_fixture(
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED
    )
    with pytest.raises(PackageRegistrationError, match="binding_invalid"):
        await register_package(
            hardware_service,
            hardware_publication,
            hardware_policy,
            actor=development_actor,
        )

    non_human_service, _, non_human_publication, non_human_policy, _ = await registration_fixture()
    with pytest.raises(PackageRegistrationError, match="human_required"):
        await register_package(
            non_human_service,
            non_human_publication,
            non_human_policy,
            actor=replace(
                registration_operator(),
                kind=SubjectKind.SERVICE,
                authentication_method=AuthenticationMethod.WORKLOAD_TOKEN,
            ),
        )


@pytest.mark.asyncio
async def test_registration_enforces_exact_binding_and_complete_actor_separation() -> None:
    service, publication_service, publication, policy, _ = await registration_fixture()
    _, _, source_actors = await publication_service.package_registration_source(
        receipt_id=publication.receipt_id
    )
    for subject_id in (*sorted(source_actors), policy.signed_by, policy.reader_workload_id):
        with pytest.raises(PackageRegistrationError, match="separation_required"):
            await register_package(
                service,
                publication,
                policy,
                actor=registration_operator(subject_id),
                key=f"register-{subject_id}",
            )

    with pytest.raises(PackageRegistrationError, match="binding_invalid"):
        await service.create(
            actor=registration_operator(),
            source_publication_receipt_id=publication.receipt_id,
            source_publication_receipt_digest="f" * 64,
            package_digest=publication.package_digest,
            registration_policy_id=policy.policy_id,
            registration_policy_digest=policy.canonical_digest,
            purpose=(
                "Register this exact published package without installation or runtime authority."
            ),
            acknowledged_registration_grants_no_installation_or_runtime_authority=True,
            idempotency_key="package-registration-binding",
            correlation_id="cor_package_registration",
        )

    hardware_service, _, hardware_publication, hardware_policy, _ = await registration_fixture(
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED
    )
    with pytest.raises(PackageRegistrationError, match="binding_invalid"):
        await register_package(hardware_service, hardware_publication, hardware_policy)


@pytest.mark.asyncio
async def test_required_audits_precede_registry_read_and_record_persistence() -> None:
    first, _, publication, policy, publisher = await registration_fixture(
        audit_sink=FailingAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await register_package(first, publication, policy)
    assert publisher.read_invocation_count == 0
    assert first.repository._records == {}  # type: ignore[attr-defined]

    second_audit = FailSecondAuditSink()
    second, _, publication, policy, publisher = await registration_fixture(audit_sink=second_audit)
    with pytest.raises(RuntimeError, match="completion audit unavailable"):
        await register_package(second, publication, policy)
    assert publisher.read_invocation_count == 1
    assert second.repository._records == {}  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_inspector_rejects_compressed_or_active_manifest_content() -> None:
    _, _, publication, policy, publisher = await registration_fixture()
    content = publisher._content[publication.package_digest]
    with zipfile.ZipFile(io.BytesIO(content), mode="r") as source:
        entries = {item.filename: source.read(item) for item in source.infolist()}
    compressed = io.BytesIO()
    with zipfile.ZipFile(compressed, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, value in entries.items():
            archive.writestr(path, value)
    inspector = BoundedConnectorPackageManifestInspector()
    with pytest.raises(PackageRegistrationError, match="archive_invalid"):
        inspector.inspect(content=compressed.getvalue(), policy=policy)

    active = io.BytesIO()
    with zipfile.ZipFile(active, mode="w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("atlas-connector.yaml", "!!python/object/apply:os.system ['whoami']")
    with pytest.raises(PackageRegistrationError, match="manifest_invalid"):
        inspector.inspect(content=active.getvalue(), policy=policy)


@pytest.mark.asyncio
async def test_package_registration_postgres_round_trip_preserves_internal_evidence() -> None:
    service, _, publication, policy, _ = await registration_fixture()
    record = await register_package(service, publication, policy)
    raw = PackageRegistrationService._normalize(asdict(record))
    assert isinstance(raw, dict)
    restored = PostgreSQLPackageRegistrationRepository._to_domain(raw)
    assert restored == record
    assert restored.manifest.network_destinations == record.manifest.network_destinations


def test_package_registration_api_requires_csrf_and_minimizes_response(tmp_path: Path) -> None:
    service, publication_service, publication, policy, _ = asyncio.run(registration_fixture())
    subject = registration_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-registration-input.v1",
        "source_publication_receipt_id": publication.receipt_id,
        "source_publication_receipt_digest": publication.canonical_digest,
        "package_digest": publication.package_digest,
        "registration_policy_id": policy.policy_id,
        "registration_policy_digest": policy.canonical_digest,
        "purpose": (
            "Register this exact published package without installation or runtime authority."
        ),
        "acknowledged_registration_grants_no_installation_or_runtime_authority": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            registry_publication_service=publication_service,
            package_registration_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-registration-records"
        denied = client.post(
            endpoint, json=payload, headers={"Idempotency-Key": "register-api-001"}
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "register-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        record_id = created.json()["data"]["record_id"]
        read = client.get(f"{endpoint}/{record_id}")

    assert denied.status_code == 403 and read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["connector_registered"] is True and data["connector_installed"] is False
    assert data["execution_authorized"] is False
    assert data["manifest"]["network_destination_count"] == 1
    rendered = created.text.lower()
    for forbidden in (
        "artifact_reference",
        "package_bytes",
        "signature_value",
        "key_material",
        "reader_workload_id",
        "network_destinations",
        "configuration_keys",
        "secret_reference_ids",
        "request_fingerprint",
        "idempotency_key",
        "lab-api.example.invalid",
    ):
        assert forbidden not in rendered
