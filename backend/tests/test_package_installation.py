from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_registration import (
    register_package,
    registration_fixture,
    registration_operator,
)

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.modules.connectors.adapters.package_installation_memory import (
    InMemoryNonExecutingPackageInstaller,
    InMemoryPackageInstallationPolicySource,
    InMemoryPackageInstallationRepository,
)
from atlas.modules.connectors.adapters.package_installation_postgres import (
    PostgreSQLPackageInstallationRepository,
)
from atlas.modules.connectors.adapters.package_registration_inspector import (
    BoundedConnectorPackageManifestInspector,
)
from atlas.modules.connectors.adapters.registry_publication_memory import (
    InMemoryNonProductionRegistryPublisher,
)
from atlas.modules.connectors.application.package_installation import (
    PackageInstallationService,
    build_development_package_installation_policy,
)
from atlas.modules.connectors.application.package_installation_ports import (
    PackageInstallationError,
)
from atlas.modules.connectors.application.package_registration import PackageRegistrationService
from atlas.modules.connectors.application.registry_publication import RegistryPublicationService
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationPolicySnapshot,
    ConnectorPackageInstallationReceipt,
)
from atlas.modules.connectors.domain.package_registration import ConnectorPackageRegistrationRecord
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


def installation_operator(
    subject_id: str = "subject.package-independent-installer",
) -> AuthenticatedSubject:
    return registration_operator(subject_id)


async def installation_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | FailSecondAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    PackageInstallationService,
    PackageRegistrationService,
    RegistryPublicationService,
    ConnectorPackageRegistrationRecord,
    ConnectorPackageInstallationPolicySnapshot,
    InMemoryNonExecutingPackageInstaller,
    InMemoryNonProductionRegistryPublisher,
]:
    (
        registration_service,
        publication_service,
        publication,
        registration_policy,
        publisher,
    ) = await registration_fixture()
    registration = await register_package(registration_service, publication, registration_policy)
    policy = build_development_package_installation_policy(
        organization_id=registration.organization_id,
        environment_id=registration.environment_id,
        issued_at=registration.registered_at - timedelta(hours=1),
        expires_at=registration.registered_at + timedelta(days=2),
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
            canonical_digest=PackageInstallationService._digest(
                PackageInstallationService._normalize(payload)
            ),
        )
    installer = InMemoryNonExecutingPackageInstaller()
    service = PackageInstallationService(
        repository=InMemoryPackageInstallationRepository(),
        registration_source=registration_service,
        policy_source=InMemoryPackageInstallationPolicySource((policy,)),
        artifact_reader=publisher,
        manifest_inspector=BoundedConnectorPackageManifestInspector(),
        installer=installer,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=registration.environment_id,
        clock=lambda: registration.registered_at,
    )
    return (
        service,
        registration_service,
        publication_service,
        registration,
        policy,
        installer,
        publisher,
    )


async def install_package(
    service: PackageInstallationService,
    registration: ConnectorPackageRegistrationRecord,
    policy: ConnectorPackageInstallationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "package-installation-001",
) -> ConnectorPackageInstallationReceipt:
    return await service.create(
        actor=actor or installation_operator(),
        source_registration_record_id=registration.record_id,
        source_registration_record_digest=registration.canonical_digest,
        package_digest=registration.package_digest,
        installation_policy_id=policy.policy_id,
        installation_policy_digest=policy.canonical_digest,
        purpose="Install this exact package without instance, target, or runtime authority.",
        acknowledged_installation_grants_no_instance_or_runtime_authority=True,
        idempotency_key=key,
        correlation_id="cor_package_installation",
    )


@pytest.mark.asyncio
async def test_installation_grants_only_instance_governance_eligibility() -> None:
    audit = CollectingAuditSink()
    service, _, _, registration, policy, installer, _ = await installation_fixture(audit_sink=audit)

    receipt = await install_package(service, registration, policy)
    repeated = await install_package(service, registration, policy)

    assert receipt.package_published and receipt.connector_registered
    assert receipt.package_installed and receipt.eligible_for_instance_governance
    assert repeated.reused and repeated.receipt_id == receipt.receipt_id
    assert installer.invocation_count == 1
    assert receipt.installation.package_digest == registration.package_digest
    assert not receipt.instance_created and not receipt.connector_enabled
    assert not receipt.target_configured and not receipt.credentials_resolved
    assert not receipt.runtime_trust_granted and not receipt.execution_authorized
    assert not receipt.deployment_approved and not receipt.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == [
        "connector_package_installation_requested",
        "connector_package_installation_completed",
    ]


@pytest.mark.asyncio
async def test_installation_optional_step_up_policy_and_human_boundary() -> None:
    service, _, _, registration, policy, _, _ = await installation_fixture()
    development_actor = replace(
        installation_operator(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    receipt = await install_package(service, registration, policy, actor=development_actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert receipt.installed_by == development_actor.subject_id

    (
        hardware_service,
        _,
        _,
        hardware_registration,
        hardware_policy,
        _,
        _,
    ) = await installation_fixture(required_assurance_level=AssuranceLevel.HARDWARE_BACKED)
    with pytest.raises(PackageInstallationError, match="binding_invalid"):
        await install_package(
            hardware_service,
            hardware_registration,
            hardware_policy,
            actor=development_actor,
        )

    (
        non_human_service,
        _,
        _,
        non_human_registration,
        non_human_policy,
        _,
        _,
    ) = await installation_fixture()
    with pytest.raises(PackageInstallationError, match="human_required"):
        await install_package(
            non_human_service,
            non_human_registration,
            non_human_policy,
            actor=replace(
                installation_operator(),
                kind=SubjectKind.SERVICE,
                authentication_method=AuthenticationMethod.WORKLOAD_TOKEN,
            ),
        )


@pytest.mark.asyncio
async def test_installation_enforces_binding_assurance_and_complete_actor_separation() -> None:
    service, registration_service, _, registration, policy, _, _ = await installation_fixture()
    _, _, _, source_actors = await registration_service.package_installation_source(
        record_id=registration.record_id
    )
    for subject_id in (
        *sorted(source_actors),
        policy.signed_by,
        policy.reader_workload_id,
        policy.installer_workload_id,
        policy.installation_custodian_id,
    ):
        with pytest.raises(PackageInstallationError, match="separation_required"):
            await install_package(
                service,
                registration,
                policy,
                actor=installation_operator(subject_id),
                key=f"install-{subject_id}",
            )

    with pytest.raises(PackageInstallationError, match="binding_invalid"):
        await service.create(
            actor=installation_operator(),
            source_registration_record_id=registration.record_id,
            source_registration_record_digest="f" * 64,
            package_digest=registration.package_digest,
            installation_policy_id=policy.policy_id,
            installation_policy_digest=policy.canonical_digest,
            purpose="Install this exact package without instance, target, or runtime authority.",
            acknowledged_installation_grants_no_instance_or_runtime_authority=True,
            idempotency_key="package-installation-binding",
            correlation_id="cor_package_installation",
        )

    (
        tampered_service,
        tampered_source,
        _,
        tampered_registration,
        tampered_policy,
        _,
        _,
    ) = await installation_fixture()
    tampered_registration = replace(
        tampered_registration,
        source_signing_receipt_digest="f" * 64,
        canonical_digest="0" * 64,
    )
    tampered_registration = replace(
        tampered_registration,
        canonical_digest=PackageRegistrationService._digest(
            PackageRegistrationService._record_payload(tampered_registration)
        ),
    )
    tampered_source.repository._records[tampered_registration.record_id] = (  # type: ignore[attr-defined]
        tampered_registration
    )
    with pytest.raises(PackageInstallationError, match="source_not_found"):
        await install_package(tampered_service, tampered_registration, tampered_policy)

    (
        hardware_service,
        _,
        _,
        hardware_registration,
        hardware_policy,
        _,
        _,
    ) = await installation_fixture(required_assurance_level=AssuranceLevel.HARDWARE_BACKED)
    with pytest.raises(PackageInstallationError, match="binding_invalid"):
        await install_package(hardware_service, hardware_registration, hardware_policy)


@pytest.mark.asyncio
async def test_required_audits_precede_artifact_read_installer_and_persistence() -> None:
    first, _, _, registration, policy, installer, publisher = await installation_fixture(
        audit_sink=FailingAuditSink()
    )
    reads_before = publisher.read_invocation_count
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await install_package(first, registration, policy)
    assert publisher.read_invocation_count == reads_before
    assert installer.invocation_count == 0
    assert first.repository._receipts == {}  # type: ignore[attr-defined]

    second_audit = FailSecondAuditSink()
    second, _, _, registration, policy, installer, publisher = await installation_fixture(
        audit_sink=second_audit
    )
    reads_before = publisher.read_invocation_count
    with pytest.raises(RuntimeError, match="completion audit unavailable"):
        await install_package(second, registration, policy)
    assert publisher.read_invocation_count == reads_before + 1
    assert installer.invocation_count == 1
    assert second.repository._receipts == {}  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_installation_rejects_changed_registry_bytes_before_installer() -> None:
    service, _, _, registration, policy, installer, publisher = await installation_fixture()
    publisher._content[registration.package_digest] = b"changed"

    with pytest.raises(PackageInstallationError, match="archive_integrity_failed"):
        await install_package(service, registration, policy)

    assert installer.invocation_count == 0
    assert service.repository._receipts == {}  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_package_installation_postgres_round_trip_preserves_internal_evidence() -> None:
    service, _, _, registration, policy, _, _ = await installation_fixture()
    receipt = await install_package(service, registration, policy)
    raw = PackageInstallationService._normalize(asdict(receipt))
    assert isinstance(raw, dict)
    restored = PostgreSQLPackageInstallationRepository._to_domain(raw)
    assert restored == receipt
    assert restored.installation.artifact_reference == receipt.installation.artifact_reference


def test_package_installation_api_requires_csrf_and_minimizes_response(tmp_path: Path) -> None:
    (
        service,
        registration_service,
        publication_service,
        registration,
        policy,
        _,
        _,
    ) = asyncio.run(installation_fixture())
    subject = installation_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-package-installation-input.v1",
        "source_registration_record_id": registration.record_id,
        "source_registration_record_digest": registration.canonical_digest,
        "package_digest": registration.package_digest,
        "installation_policy_id": policy.policy_id,
        "installation_policy_digest": policy.canonical_digest,
        "purpose": "Install this exact package without instance, target, or runtime authority.",
        "acknowledged_installation_grants_no_instance_or_runtime_authority": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            registry_publication_service=publication_service,
            package_registration_service=registration_service,
            package_installation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/package-installation-receipts"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "install-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "artifact_reference": "installation://caller-selected"},
            headers={
                "Idempotency-Key": "install-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "install-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        receipt_id = created.json()["data"]["receipt_id"]
        read = client.get(f"{endpoint}/{receipt_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["package_installed"] is True and data["instance_created"] is False
    assert data["execution_authorized"] is False
    rendered = created.text.lower()
    for hidden in (
        'artifact_reference"',
        "installation://",
        "package_bytes",
        "signature_value",
        "key_material",
        "installer_workload_id",
        "installation_custodian_id",
        "request_fingerprint",
        "idempotency_key",
    ):
        assert hidden not in rendered
