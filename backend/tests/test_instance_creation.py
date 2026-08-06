from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_package_installation import (
    install_package,
    installation_fixture,
    installation_operator,
)

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.modules.connectors.adapters.instance_creation_memory import (
    InMemoryConnectorInstanceCreationPolicySource,
    InMemoryConnectorInstanceRepository,
)
from atlas.modules.connectors.adapters.instance_creation_postgres import (
    PostgreSQLConnectorInstanceRepository,
)
from atlas.modules.connectors.application.instance_creation import (
    ConnectorInstanceCreationService,
    build_development_connector_instance_creation_policy,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceCreationError,
)
from atlas.modules.connectors.application.package_installation import PackageInstallationService
from atlas.modules.connectors.application.package_registration import PackageRegistrationService
from atlas.modules.connectors.application.registry_publication import RegistryPublicationService
from atlas.modules.connectors.domain.instance_creation import (
    ConnectorInstanceCreationPolicySnapshot,
    ConnectorInstanceRecord,
)
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationReceipt,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject


class FailSecondAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, record: AuditRecord) -> None:
        self.records.append(record)
        if len(self.records) == 2:
            raise RuntimeError("completion audit unavailable")


def instance_operator(
    subject_id: str = "subject.connector-independent-instance-creator",
) -> AuthenticatedSubject:
    return installation_operator(subject_id)


async def instance_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | FailSecondAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.MULTI_FACTOR,
) -> tuple[
    ConnectorInstanceCreationService,
    PackageInstallationService,
    PackageRegistrationService,
    RegistryPublicationService,
    ConnectorPackageInstallationReceipt,
    ConnectorInstanceCreationPolicySnapshot,
]:
    (
        installation_service,
        registration_service,
        publication_service,
        registration,
        installation_policy,
        _,
        _,
    ) = await installation_fixture()
    installation = await install_package(
        installation_service,
        registration,
        installation_policy,
    )
    policy = build_development_connector_instance_creation_policy(
        organization_id=installation.organization_id,
        environment_id=installation.environment_id,
        issued_at=installation.installed_at - timedelta(hours=1),
        expires_at=installation.installed_at + timedelta(days=2),
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
            canonical_digest=ConnectorInstanceCreationService._digest(
                ConnectorInstanceCreationService._normalize(payload)
            ),
        )
    service = ConnectorInstanceCreationService(
        repository=InMemoryConnectorInstanceRepository(),
        installation_source=installation_service,
        policy_source=InMemoryConnectorInstanceCreationPolicySource((policy,)),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=installation.environment_id,
        clock=lambda: installation.installed_at,
    )
    return (
        service,
        installation_service,
        registration_service,
        publication_service,
        installation,
        policy,
    )


async def create_instance(
    service: ConnectorInstanceCreationService,
    installation: ConnectorPackageInstallationReceipt,
    policy: ConnectorInstanceCreationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "connector-instance-create-001",
    instance_key: str = "storage-east",
) -> ConnectorInstanceRecord:
    return await service.create(
        actor=actor or instance_operator(),
        source_installation_receipt_id=installation.receipt_id,
        source_installation_receipt_digest=installation.canonical_digest,
        package_digest=installation.package_digest,
        instance_key=instance_key,
        display_name=f"Instance {instance_key}",
        instance_policy_id=policy.policy_id,
        instance_policy_digest=policy.canonical_digest,
        purpose="Create a disabled connector instance without target or runtime authority.",
        acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority=True,
        idempotency_key=key,
        correlation_id="cor_connector_instance",
    )


@pytest.mark.asyncio
async def test_instance_creation_grants_only_configuration_governance_eligibility() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, installation, policy = await instance_fixture(audit_sink=audit)

    record = await create_instance(service, installation, policy)
    repeated = await create_instance(service, installation, policy)
    second = await create_instance(
        service,
        installation,
        policy,
        key="connector-instance-create-002",
        instance_key="storage-west",
    )

    assert record.package_installed and record.instance_created
    assert record.eligible_for_configuration_governance
    assert record.instance_state == "disabled_unconfigured"
    assert repeated.reused and repeated.record_id == record.record_id
    assert second.record_id != record.record_id
    assert not record.target_configured and not record.credentials_resolved
    assert not record.connector_enabled and not record.runtime_trust_granted
    assert not record.execution_authorized and not record.deployment_approved
    assert not record.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == [
        "connector_instance_creation_requested",
        "connector_instance_creation_completed",
        "connector_instance_creation_requested",
        "connector_instance_creation_completed",
    ]


@pytest.mark.asyncio
async def test_instance_creation_enforces_source_binding_assurance_and_actor_separation() -> None:
    service, installation_service, _, _, installation, policy = await instance_fixture()
    _, _, _, source_actors = await installation_service.connector_instance_creation_source(
        receipt_id=installation.receipt_id
    )
    for subject_id in (*sorted(source_actors), policy.signed_by):
        with pytest.raises(ConnectorInstanceCreationError, match="separation_required"):
            await create_instance(
                service,
                installation,
                policy,
                actor=instance_operator(subject_id),
                key=f"instance-{subject_id}",
            )

    with pytest.raises(ConnectorInstanceCreationError, match="binding_invalid"):
        await service.create(
            actor=instance_operator(),
            source_installation_receipt_id=installation.receipt_id,
            source_installation_receipt_digest="f" * 64,
            package_digest=installation.package_digest,
            instance_key="storage-binding",
            display_name="Storage binding check",
            instance_policy_id=policy.policy_id,
            instance_policy_digest=policy.canonical_digest,
            purpose="Create a disabled connector instance without target or runtime authority.",
            acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority=True,
            idempotency_key="connector-instance-binding",
            correlation_id="cor_connector_instance",
        )

    tampered_service, source, _, _, tampered, tampered_policy = await instance_fixture()
    changed_result = replace(
        tampered.installation,
        installation_store_profile_id="installation-store.unexpected",
    )
    tampered = replace(tampered, installation=changed_result, canonical_digest="0" * 64)
    tampered = replace(
        tampered,
        canonical_digest=PackageInstallationService._digest(
            PackageInstallationService._receipt_payload(tampered)
        ),
    )
    source.repository._receipts[tampered.receipt_id] = tampered  # type: ignore[attr-defined]
    with pytest.raises(ConnectorInstanceCreationError, match="source_not_found"):
        await create_instance(tampered_service, tampered, tampered_policy)

    (
        missing_service,
        _,
        missing_registration_source,
        _,
        missing,
        missing_policy,
    ) = await instance_fixture()
    missing_registration_source.repository._records.pop(  # type: ignore[attr-defined]
        missing.source_registration_record_id
    )
    with pytest.raises(ConnectorInstanceCreationError, match="source_not_found"):
        await create_instance(missing_service, missing, missing_policy)

    hardware_service, _, _, _, hardware_installation, hardware_policy = await instance_fixture(
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED
    )
    with pytest.raises(ConnectorInstanceCreationError, match="binding_invalid"):
        await create_instance(hardware_service, hardware_installation, hardware_policy)


@pytest.mark.asyncio
async def test_instance_required_audits_precede_persistence() -> None:
    first, _, _, _, installation, policy = await instance_fixture(audit_sink=FailingAuditSink())
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await create_instance(first, installation, policy)
    assert first.repository._records == {}  # type: ignore[attr-defined]

    second, _, _, _, installation, policy = await instance_fixture(audit_sink=FailSecondAuditSink())
    with pytest.raises(RuntimeError, match="completion audit unavailable"):
        await create_instance(second, installation, policy)
    assert second.repository._records == {}  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_instance_scope_key_conflict_fails_but_same_installation_allows_distinct_keys() -> (
    None
):
    service, _, _, _, installation, policy = await instance_fixture()
    await create_instance(service, installation, policy)

    with pytest.raises(ConnectorInstanceCreationError, match="key_conflict"):
        await create_instance(
            service,
            installation,
            policy,
            actor=instance_operator("subject.second-instance-creator"),
            key="connector-instance-create-conflict",
        )


@pytest.mark.asyncio
async def test_connector_instance_postgres_round_trip_preserves_internal_lineage() -> None:
    service, _, _, _, installation, policy = await instance_fixture()
    record = await create_instance(service, installation, policy)
    raw = ConnectorInstanceCreationService._normalize(asdict(record))
    assert isinstance(raw, dict)
    restored = PostgreSQLConnectorInstanceRepository._to_domain(raw)
    assert restored == record
    assert (
        restored.source_registration_record_digest == installation.source_registration_record_digest
    )


def test_connector_instance_api_requires_csrf_and_minimizes_response(tmp_path: Path) -> None:
    (
        service,
        installation_service,
        registration_service,
        publication_service,
        installation,
        policy,
    ) = asyncio.run(instance_fixture())
    subject = instance_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-instance-creation-input.v1",
        "source_installation_receipt_id": installation.receipt_id,
        "source_installation_receipt_digest": installation.canonical_digest,
        "package_digest": installation.package_digest,
        "instance_key": "storage-east",
        "display_name": "Storage East",
        "instance_policy_id": policy.policy_id,
        "instance_policy_digest": policy.canonical_digest,
        "purpose": "Create a disabled connector instance without target or runtime authority.",
        "acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            registry_publication_service=publication_service,
            package_registration_service=registration_service,
            package_installation_service=installation_service,
            connector_instance_creation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/instances"
        denied = client.post(
            endpoint, json=payload, headers={"Idempotency-Key": "instance-api-001"}
        )
        forbidden = client.post(
            endpoint,
            json={**payload, "target_endpoint": "https://caller-selected.example"},
            headers={
                "Idempotency-Key": "instance-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "instance-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        record_id = created.json()["data"]["record_id"]
        read = client.get(f"{endpoint}/{record_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["instance_state"] == "disabled_unconfigured"
    assert data["instance_created"] is True and data["connector_enabled"] is False
    assert data["execution_authorized"] is False
    rendered = created.text.lower()
    for hidden in (
        "artifact_reference",
        "installation-store",
        "installer_workload_id",
        "installation_custodian_id",
        "request_fingerprint",
        "idempotency_key",
        "target_endpoint",
        "secret_reference",
    ):
        assert hidden not in rendered
