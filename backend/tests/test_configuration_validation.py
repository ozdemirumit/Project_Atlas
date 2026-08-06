from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_credential_assignment import (
    assign_credential,
    credential_assignment_fixture,
)
from test_instance_creation import instance_operator
from test_package_acquisition import CollectingAuditSink, FailingAuditSink

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.configuration_validation_memory import (
    InMemoryConnectorConfigurationEvidenceSource,
    InMemoryConnectorConfigurationValidationPolicySource,
    InMemoryConnectorConfigurationValidationRepository,
)
from atlas.modules.connectors.adapters.configuration_validation_postgres import (
    PostgreSQLConnectorConfigurationValidationRepository,
)
from atlas.modules.connectors.application.configuration_validation import (
    ConnectorConfigurationValidationService,
    _signed_snapshot,
    build_development_connector_configuration_evidence,
    build_development_connector_configuration_validation_policy,
)
from atlas.modules.connectors.application.configuration_validation_ports import (
    ConnectorConfigurationValidationError,
)
from atlas.modules.connectors.application.credential_assignment import (
    ConnectorCredentialAssignmentService,
)
from atlas.modules.connectors.application.instance_creation import ConnectorInstanceCreationService
from atlas.modules.connectors.application.package_installation import PackageInstallationService
from atlas.modules.connectors.application.package_registration import PackageRegistrationService
from atlas.modules.connectors.application.target_configuration import (
    ConnectorTargetConfigurationService,
)
from atlas.modules.connectors.domain.configuration_validation import (
    ConnectorConfigurationEvidenceSnapshot,
    ConnectorConfigurationValidationPolicySnapshot,
    ConnectorConfigurationValidationRecord,
)
from atlas.modules.connectors.domain.credential_assignment import (
    ConnectorCredentialAssignmentRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


def configuration_validator(
    subject_id: str = "subject.connector-independent-configuration-validator",
) -> AuthenticatedSubject:
    return instance_operator(subject_id)


async def configuration_validation_fixture(
    *, audit_sink: CollectingAuditSink | FailingAuditSink | None = None
) -> tuple[
    ConnectorConfigurationValidationService,
    ConnectorCredentialAssignmentService,
    ConnectorTargetConfigurationService,
    ConnectorInstanceCreationService,
    PackageInstallationService,
    PackageRegistrationService,
    ConnectorCredentialAssignmentRecord,
    ConnectorConfigurationEvidenceSnapshot,
    ConnectorConfigurationValidationPolicySnapshot,
]:
    (
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        binding,
        credential_profile,
        credential_policy,
    ) = await credential_assignment_fixture()
    assignment = await assign_credential(
        assignment_service, binding, credential_profile, credential_policy
    )
    evidence = build_development_connector_configuration_evidence(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        source_assignment_id=assignment.assignment_id,
        source_assignment_digest=assignment.canonical_digest,
        package_digest=assignment.package_digest,
        instance_id=assignment.instance_id,
        target_profile_id=assignment.target_profile_id,
        credential_profile_id=assignment.credential_profile_id,
        target_type=assignment.target_type,
        target_product=assignment.target_product,
        issued_at=assignment.assigned_at,
        expires_at=assignment.assigned_at + timedelta(days=10),
    )
    policy = build_development_connector_configuration_validation_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=assignment.assigned_at - timedelta(hours=1),
        expires_at=assignment.assigned_at + timedelta(days=10),
    )
    service = ConnectorConfigurationValidationService(
        repository=InMemoryConnectorConfigurationValidationRepository(),
        assignment_source=assignment_service,
        evidence_source=InMemoryConnectorConfigurationEvidenceSource((evidence,)),
        policy_source=InMemoryConnectorConfigurationValidationPolicySource((policy,)),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.assigned_at,
    )
    return (
        service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        assignment,
        evidence,
        policy,
    )


async def validate_configuration(
    service: ConnectorConfigurationValidationService,
    assignment: ConnectorCredentialAssignmentRecord,
    evidence: ConnectorConfigurationEvidenceSnapshot,
    policy: ConnectorConfigurationValidationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "configuration-validation-001",
) -> ConnectorConfigurationValidationRecord:
    return await service.create(
        actor=actor or configuration_validator(),
        source_assignment_id=assignment.assignment_id,
        source_assignment_digest=assignment.canonical_digest,
        package_digest=assignment.package_digest,
        evidence_id=evidence.evidence_id,
        evidence_digest=evidence.canonical_digest,
        validation_policy_id=policy.policy_id,
        validation_policy_digest=policy.canonical_digest,
        purpose="Verify bounded signed configuration evidence without runtime authority.",
        acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority=True,
        idempotency_key=key,
        correlation_id="cor_configuration_validation",
    )


@pytest.mark.asyncio
async def test_validation_grants_only_capability_governance_eligibility() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, _, _, assignment, evidence, policy = await configuration_validation_fixture(
        audit_sink=audit
    )
    record = await validate_configuration(service, assignment, evidence, policy)
    repeated = await validate_configuration(service, assignment, evidence, policy)

    assert record.configuration_validated and record.connectivity_evidence_verified
    assert record.eligible_for_capability_governance
    assert record.instance_state == "disabled_configuration_validated"
    assert repeated.reused and repeated.validation_id == record.validation_id
    assert not record.credentials_resolved and not record.connector_enabled
    assert not record.runtime_trust_granted and not record.execution_authorized
    assert [item.result_code for item in audit.records] == [
        "connector_configuration_validation_requested",
        "connector_configuration_validation_completed",
    ]


@pytest.mark.asyncio
async def test_validation_enforces_exact_lineage_results_and_separation() -> None:
    (
        service,
        assignment_service,
        _,
        _,
        _,
        _,
        assignment,
        evidence,
        policy,
    ) = await configuration_validation_fixture()
    _, actors = await assignment_service.configuration_validation_source(
        assignment_id=assignment.assignment_id
    )
    for subject_id in (*sorted(actors), evidence.signed_by, policy.signed_by):
        with pytest.raises(ConnectorConfigurationValidationError, match="separation_required"):
            await validate_configuration(
                service,
                assignment,
                evidence,
                policy,
                actor=configuration_validator(subject_id),
                key=f"configuration-{subject_id}",
            )
    with pytest.raises(ConnectorConfigurationValidationError, match="invalid"):
        await service.create(
            actor=configuration_validator(),
            source_assignment_id=assignment.assignment_id,
            source_assignment_digest="f" * 64,
            package_digest=assignment.package_digest,
            evidence_id=evidence.evidence_id,
            evidence_digest=evidence.canonical_digest,
            validation_policy_id=policy.policy_id,
            validation_policy_digest=policy.canonical_digest,
            purpose="Reject mismatched immutable configuration validation lineage.",
            acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority=True,
            idempotency_key="configuration-invalid-001",
            correlation_id="cor_invalid",
        )


@pytest.mark.asyncio
async def test_validation_rejects_non_read_only_probe_evidence() -> None:
    (
        _,
        assignment_service,
        _,
        _,
        _,
        _,
        assignment,
        evidence,
        policy,
    ) = await configuration_validation_fixture()
    unsafe = replace(
        evidence,
        authorization_result="authorization.write-capable",
        canonical_digest="0" * 64,
    )
    unsafe = replace(unsafe, canonical_digest=_signed_snapshot(unsafe))
    service = ConnectorConfigurationValidationService(
        repository=InMemoryConnectorConfigurationValidationRepository(),
        assignment_source=assignment_service,
        evidence_source=InMemoryConnectorConfigurationEvidenceSource((unsafe,)),
        policy_source=InMemoryConnectorConfigurationValidationPolicySource((policy,)),
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.assigned_at,
    )
    with pytest.raises(ConnectorConfigurationValidationError, match="invalid"):
        await validate_configuration(service, assignment, unsafe, policy)


@pytest.mark.asyncio
async def test_validation_requires_audit_before_persistence() -> None:
    service, _, _, _, _, _, assignment, evidence, policy = await configuration_validation_fixture(
        audit_sink=FailingAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await validate_configuration(service, assignment, evidence, policy)
    assert (
        await service.repository.get_by_assignment(source_assignment_id=assignment.assignment_id)
        is None
    )


@pytest.mark.asyncio
async def test_validation_postgres_payload_round_trip_is_bounded() -> None:
    service, _, _, _, _, _, assignment, evidence, policy = await configuration_validation_fixture()
    record = await validate_configuration(service, assignment, evidence, policy)
    raw = ConnectorConfigurationValidationService._normalize(asdict(record))
    assert isinstance(raw, dict)
    restored = PostgreSQLConnectorConfigurationValidationRepository._to_domain(raw)
    assert restored == record
    rendered = repr(raw).lower()
    for hidden in ("endpoint_url", "target_ip", "secret_reference_id", "password", "token_value"):
        assert hidden not in rendered


def test_validation_api_rejects_raw_target_input_and_minimizes_response(
    tmp_path: Path,
) -> None:
    (
        service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        assignment,
        evidence,
        policy,
    ) = asyncio.run(configuration_validation_fixture())
    subject = configuration_validator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-configuration-validation-input.v1",
        "source_assignment_id": assignment.assignment_id,
        "source_assignment_digest": assignment.canonical_digest,
        "package_digest": assignment.package_digest,
        "evidence_id": evidence.evidence_id,
        "evidence_digest": evidence.canonical_digest,
        "validation_policy_id": policy.policy_id,
        "validation_policy_digest": policy.canonical_digest,
        "purpose": "Verify bounded signed configuration evidence without runtime authority.",
        "acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_registration_service=registration_service,
            package_installation_service=installation_service,
            connector_instance_creation_service=instance_service,
            target_configuration_service=target_service,
            credential_assignment_service=assignment_service,
            configuration_validation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/configuration-validations"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "cfg-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "endpoint_url": "https://attacker.invalid"},
            headers={
                "Idempotency-Key": "cfg-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "cfg-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        validation_id = created.json()["data"]["validation_id"]
        read = client.get(f"{endpoint}/{validation_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["configuration_validated"] is True
    assert data["credentials_resolved"] is False and data["connector_enabled"] is False
    rendered = created.text.lower()
    for hidden in (
        "endpoint_url",
        "target_ip",
        "secret_reference_id",
        "secret_store_profile_id",
        "request_fingerprint",
        "idempotency_key",
        "password",
        "token_value",
        "access_token",
    ):
        assert hidden not in rendered
