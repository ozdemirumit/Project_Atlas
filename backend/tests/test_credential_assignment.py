from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_instance_creation import instance_operator
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_target_configuration import bind_target, target_configuration_fixture

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.credential_assignment_memory import (
    InMemoryConnectorCredentialAssignmentPolicySource,
    InMemoryConnectorCredentialAssignmentRepository,
    InMemoryConnectorCredentialProfileSource,
)
from atlas.modules.connectors.adapters.credential_assignment_postgres import (
    PostgreSQLConnectorCredentialAssignmentRepository,
)
from atlas.modules.connectors.application.credential_assignment import (
    ConnectorCredentialAssignmentService,
    _signed_snapshot,
    build_development_connector_credential_assignment_policy,
    build_development_connector_credential_profile,
)
from atlas.modules.connectors.application.credential_assignment_ports import (
    ConnectorCredentialAssignmentError,
)
from atlas.modules.connectors.application.instance_creation import ConnectorInstanceCreationService
from atlas.modules.connectors.application.package_installation import PackageInstallationService
from atlas.modules.connectors.application.package_registration import PackageRegistrationService
from atlas.modules.connectors.application.target_configuration import (
    ConnectorTargetConfigurationService,
)
from atlas.modules.connectors.domain.credential_assignment import (
    ConnectorCredentialAssignmentPolicySnapshot,
    ConnectorCredentialAssignmentRecord,
    ConnectorCredentialProfileSnapshot,
)
from atlas.modules.connectors.domain.target_configuration import ConnectorTargetConfigurationBinding
from atlas.modules.identity.domain.models import AuthenticatedSubject


def credential_assigner(
    subject_id: str = "subject.connector-independent-credential-assigner",
) -> AuthenticatedSubject:
    return instance_operator(subject_id)


async def credential_assignment_fixture(
    *, audit_sink: CollectingAuditSink | FailingAuditSink | None = None
) -> tuple[
    ConnectorCredentialAssignmentService,
    ConnectorTargetConfigurationService,
    ConnectorInstanceCreationService,
    PackageInstallationService,
    PackageRegistrationService,
    ConnectorTargetConfigurationBinding,
    ConnectorCredentialProfileSnapshot,
    ConnectorCredentialAssignmentPolicySnapshot,
]:
    (
        target_service,
        instance_service,
        installation_service,
        registration_service,
        instance,
        target,
        target_policy,
    ) = await target_configuration_fixture()
    binding = await bind_target(target_service, instance, target, target_policy)
    profile = build_development_connector_credential_profile(
        organization_id=binding.organization_id,
        environment_id=binding.environment_id,
        issued_at=binding.bound_at - timedelta(hours=1),
        expires_at=binding.bound_at + timedelta(days=10),
    )
    policy = build_development_connector_credential_assignment_policy(
        organization_id=binding.organization_id,
        environment_id=binding.environment_id,
        issued_at=binding.bound_at - timedelta(hours=1),
        expires_at=binding.bound_at + timedelta(days=10),
    )
    service = ConnectorCredentialAssignmentService(
        repository=InMemoryConnectorCredentialAssignmentRepository(),
        target_source=target_service,
        credential_profile_source=InMemoryConnectorCredentialProfileSource((profile,)),
        policy_source=InMemoryConnectorCredentialAssignmentPolicySource((policy,)),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=binding.environment_id,
        clock=lambda: binding.bound_at,
    )
    return (
        service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        binding,
        profile,
        policy,
    )


async def assign_credential(
    service: ConnectorCredentialAssignmentService,
    binding: ConnectorTargetConfigurationBinding,
    profile: ConnectorCredentialProfileSnapshot,
    policy: ConnectorCredentialAssignmentPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "credential-assignment-001",
) -> ConnectorCredentialAssignmentRecord:
    return await service.create(
        actor=actor or credential_assigner(),
        source_target_binding_id=binding.binding_id,
        source_target_binding_digest=binding.canonical_digest,
        package_digest=binding.package_digest,
        credential_profile_id=profile.profile_id,
        credential_profile_digest=profile.canonical_digest,
        credential_policy_id=policy.policy_id,
        credential_policy_digest=policy.canonical_digest,
        purpose="Assign governed credential metadata without secret or runtime access.",
        acknowledged_assignment_grants_no_secret_access_enablement_or_runtime_authority=True,
        idempotency_key=key,
        correlation_id="cor_credential_assignment",
    )


@pytest.mark.asyncio
async def test_assignment_grants_only_configuration_validation_eligibility() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, _, binding, profile, policy = await credential_assignment_fixture(
        audit_sink=audit
    )
    record = await assign_credential(service, binding, profile, policy)
    repeated = await assign_credential(service, binding, profile, policy)

    assert record.credential_references_assigned
    assert record.eligible_for_configuration_validation
    assert record.instance_state == "disabled_credentials_assigned"
    assert repeated.reused and repeated.assignment_id == record.assignment_id
    assert not record.credentials_resolved and not record.connector_enabled
    assert not record.runtime_trust_granted and not record.execution_authorized
    assert [item.result_code for item in audit.records] == [
        "connector_credential_assignment_requested",
        "connector_credential_assignment_completed",
    ]
    rendered_audit = repr(audit.records).lower()
    assert profile.secret_reference_id not in rendered_audit
    assert profile.secret_store_profile_id not in rendered_audit


@pytest.mark.asyncio
async def test_assignment_enforces_exact_source_policy_profile_and_separation() -> None:
    (
        service,
        target_service,
        _,
        _,
        _,
        binding,
        profile,
        policy,
    ) = await credential_assignment_fixture()
    _, _, actors = await target_service.credential_assignment_source(binding_id=binding.binding_id)
    for subject_id in (*sorted(actors), profile.signed_by, policy.signed_by):
        with pytest.raises(ConnectorCredentialAssignmentError, match="separation_required"):
            await assign_credential(
                service,
                binding,
                profile,
                policy,
                actor=credential_assigner(subject_id),
                key=f"credential-{subject_id}",
            )
    with pytest.raises(ConnectorCredentialAssignmentError, match="invalid"):
        await service.create(
            actor=credential_assigner(),
            source_target_binding_id=binding.binding_id,
            source_target_binding_digest="f" * 64,
            package_digest=binding.package_digest,
            credential_profile_id=profile.profile_id,
            credential_profile_digest=profile.canonical_digest,
            credential_policy_id=policy.policy_id,
            credential_policy_digest=policy.canonical_digest,
            purpose="Reject mismatched immutable credential assignment lineage.",
            acknowledged_assignment_grants_no_secret_access_enablement_or_runtime_authority=True,
            idempotency_key="credential-invalid-001",
            correlation_id="cor_invalid",
        )


@pytest.mark.asyncio
async def test_assignment_rejects_privilege_outside_signed_policy() -> None:
    _, target_service, _, _, _, binding, profile, policy = await credential_assignment_fixture()
    unsafe = replace(profile, privilege_class="privilege.write", canonical_digest="0" * 64)
    unsafe = replace(unsafe, canonical_digest=_signed_snapshot(unsafe))
    service = ConnectorCredentialAssignmentService(
        repository=InMemoryConnectorCredentialAssignmentRepository(),
        target_source=target_service,
        credential_profile_source=InMemoryConnectorCredentialProfileSource((unsafe,)),
        policy_source=InMemoryConnectorCredentialAssignmentPolicySource((policy,)),
        audit_sink=CollectingAuditSink(),
        environment_id=binding.environment_id,
        clock=lambda: binding.bound_at,
    )
    with pytest.raises(ConnectorCredentialAssignmentError, match="invalid"):
        await assign_credential(service, binding, unsafe, policy)


@pytest.mark.asyncio
async def test_assignment_requires_audit_before_persistence() -> None:
    service, _, _, _, _, binding, profile, policy = await credential_assignment_fixture(
        audit_sink=FailingAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await assign_credential(service, binding, profile, policy)
    assert (
        await service.repository.get_by_target_binding(source_target_binding_id=binding.binding_id)
        is None
    )


@pytest.mark.asyncio
async def test_assignment_postgres_payload_round_trip_excludes_internal_reference() -> None:
    service, _, _, _, _, binding, profile, policy = await credential_assignment_fixture()
    record = await assign_credential(service, binding, profile, policy)
    raw = ConnectorCredentialAssignmentService._normalize(asdict(record))
    assert isinstance(raw, dict)
    restored = PostgreSQLConnectorCredentialAssignmentRepository._to_domain(raw)
    assert restored == record
    assert "secret_reference_id" not in raw and "secret_store_profile_id" not in raw


def test_assignment_api_rejects_secret_input_and_minimizes_response(tmp_path: Path) -> None:
    (
        service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        binding,
        profile,
        policy,
    ) = asyncio.run(credential_assignment_fixture())
    subject = credential_assigner()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-credential-assignment-input.v1",
        "source_target_binding_id": binding.binding_id,
        "source_target_binding_digest": binding.canonical_digest,
        "package_digest": binding.package_digest,
        "credential_profile_id": profile.profile_id,
        "credential_profile_digest": profile.canonical_digest,
        "credential_policy_id": policy.policy_id,
        "credential_policy_digest": policy.canonical_digest,
        "purpose": "Assign governed credential metadata without secret or runtime access.",
        "acknowledged_assignment_grants_no_secret_access_enablement_or_runtime_authority": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_registration_service=registration_service,
            package_installation_service=installation_service,
            connector_instance_creation_service=instance_service,
            target_configuration_service=target_service,
            credential_assignment_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/credential-assignments"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "cred-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "secret_reference_id": "secret.attacker"},
            headers={
                "Idempotency-Key": "cred-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "cred-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        assignment_id = created.json()["data"]["assignment_id"]
        read = client.get(f"{endpoint}/{assignment_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    assert created.json()["data"]["credentials_resolved"] is False
    rendered = created.text.lower()
    for hidden in (
        "secret_reference_id",
        "secret-reference.connector.storage-reader",
        "secret_store_profile_id",
        "secret-store-profile.enterprise",
        "request_fingerprint",
        "idempotency_key",
        "password",
        "token_value",
        "access_token",
    ):
        assert hidden not in rendered
