from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_configuration_validation import (
    configuration_validation_fixture,
    validate_configuration,
)
from test_instance_creation import instance_operator
from test_package_acquisition import CollectingAuditSink, FailingAuditSink

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.capability_enablement_memory import (
    InMemoryConnectorCapabilityEnablementPolicySource,
    InMemoryConnectorCapabilityEnablementRepository,
    InMemoryConnectorCapabilityProfileSource,
)
from atlas.modules.connectors.adapters.capability_enablement_postgres import (
    PostgreSQLConnectorCapabilityEnablementRepository,
)
from atlas.modules.connectors.application.capability_enablement import (
    ConnectorCapabilityEnablementService,
    _signed_snapshot,
    build_connector_capability_profile,
    build_development_connector_capability_enablement_policy,
)
from atlas.modules.connectors.application.capability_enablement_ports import (
    ConnectorCapabilityEnablementError,
)
from atlas.modules.connectors.application.configuration_validation import (
    ConnectorConfigurationValidationService,
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
from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementPolicySnapshot,
    ConnectorCapabilityEnablementRecord,
    ConnectorCapabilityProfileSnapshot,
)
from atlas.modules.connectors.domain.configuration_validation import (
    ConnectorConfigurationValidationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


def capability_enabler(
    subject_id: str = "subject.connector-independent-capability-enabler",
) -> AuthenticatedSubject:
    return instance_operator(subject_id)


async def capability_enablement_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    ConnectorCapabilityEnablementService,
    ConnectorConfigurationValidationService,
    ConnectorCredentialAssignmentService,
    ConnectorTargetConfigurationService,
    ConnectorInstanceCreationService,
    PackageInstallationService,
    PackageRegistrationService,
    ConnectorConfigurationValidationRecord,
    ConnectorCapabilityProfileSnapshot,
    ConnectorCapabilityEnablementPolicySnapshot,
]:
    (
        validation_service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        assignment,
        evidence,
        validation_policy,
    ) = await configuration_validation_fixture()
    validation = await validate_configuration(
        validation_service, assignment, evidence, validation_policy
    )
    _, registration, _ = await validation_service.capability_enablement_source(
        validation_id=validation.validation_id
    )
    profile = build_connector_capability_profile(
        validation=validation,
        registration=registration,
        issued_at=validation.validated_at,
        expires_at=validation.validated_at + timedelta(days=10),
    )
    policy = build_development_connector_capability_enablement_policy(
        organization_id=validation.organization_id,
        environment_id=validation.environment_id,
        issued_at=validation.validated_at - timedelta(hours=1),
        expires_at=validation.validated_at + timedelta(days=10),
    )
    if required_assurance_level is not policy.required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_snapshot(policy))
    service = ConnectorCapabilityEnablementService(
        repository=InMemoryConnectorCapabilityEnablementRepository(),
        validation_source=validation_service,
        profile_source=InMemoryConnectorCapabilityProfileSource((profile,)),
        policy_source=InMemoryConnectorCapabilityEnablementPolicySource((policy,)),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=validation.environment_id,
        clock=lambda: validation.validated_at,
    )
    return (
        service,
        validation_service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        validation,
        profile,
        policy,
    )


async def enable_capabilities(
    service: ConnectorCapabilityEnablementService,
    validation: ConnectorConfigurationValidationRecord,
    profile: ConnectorCapabilityProfileSnapshot,
    policy: ConnectorCapabilityEnablementPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "capability-enablement-001",
) -> ConnectorCapabilityEnablementRecord:
    return await service.create(
        actor=actor or capability_enabler(),
        source_validation_id=validation.validation_id,
        source_validation_digest=validation.canonical_digest,
        package_digest=validation.package_digest,
        capability_profile_id=profile.profile_id,
        capability_profile_digest=profile.canonical_digest,
        enablement_policy_id=policy.policy_id,
        enablement_policy_digest=policy.canonical_digest,
        purpose="Enable exact governed read-only capabilities without runtime authority.",
        acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority=True,
        idempotency_key=key,
        correlation_id="cor_capability_enablement",
    )


@pytest.mark.asyncio
async def test_enablement_grants_only_runtime_trust_eligibility() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, _, _, _, validation, profile, policy = await capability_enablement_fixture(
        audit_sink=audit
    )
    record = await enable_capabilities(service, validation, profile, policy)
    repeated = await enable_capabilities(service, validation, profile, policy)

    assert record.capability_governance_applied and record.connector_enabled
    assert record.eligible_for_runtime_trust
    assert record.instance_state == "enabled_capabilities_governed"
    assert repeated.reused and repeated.enablement_id == record.enablement_id
    assert not record.credentials_resolved and not record.runtime_trust_granted
    assert not record.execution_authorized and not record.deployment_approved
    assert [item.result_code for item in audit.records] == [
        "connector_capability_enablement_requested",
        "connector_capability_enablement_completed",
    ]


@pytest.mark.asyncio
async def test_enablement_accepts_development_identity_under_default_policy() -> None:
    service, _, _, _, _, _, _, validation, profile, policy = await capability_enablement_fixture()
    development_actor = replace(
        capability_enabler(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    record = await enable_capabilities(
        service, validation, profile, policy, actor=development_actor
    )

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.enabled_by == development_actor.subject_id


@pytest.mark.parametrize(
    "required_assurance_level",
    [AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED],
)
@pytest.mark.asyncio
async def test_enablement_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, _, _, _, _, _, validation, profile, policy = await capability_enablement_fixture(
        required_assurance_level=required_assurance_level
    )
    development_actor = replace(
        capability_enabler(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(ConnectorCapabilityEnablementError, match="invalid"):
        await enable_capabilities(service, validation, profile, policy, actor=development_actor)


@pytest.mark.asyncio
async def test_enablement_rejects_non_human_actor() -> None:
    service, _, _, _, _, _, _, validation, profile, policy = await capability_enablement_fixture()
    service_actor = replace(
        capability_enabler(),
        kind=SubjectKind.SERVICE,
        authentication_method=AuthenticationMethod.WORKLOAD_TOKEN,
    )

    with pytest.raises(ConnectorCapabilityEnablementError, match="human_required"):
        await enable_capabilities(service, validation, profile, policy, actor=service_actor)


@pytest.mark.asyncio
async def test_enablement_enforces_exact_lineage_manifest_and_separation() -> None:
    (
        service,
        validation_service,
        _,
        _,
        _,
        _,
        _,
        validation,
        profile,
        policy,
    ) = await capability_enablement_fixture()
    _, _, actors = await validation_service.capability_enablement_source(
        validation_id=validation.validation_id
    )
    for subject_id in (*sorted(actors), profile.signed_by, policy.signed_by):
        with pytest.raises(ConnectorCapabilityEnablementError, match="separation_required"):
            await enable_capabilities(
                service,
                validation,
                profile,
                policy,
                actor=capability_enabler(subject_id),
                key=f"capability-{subject_id}",
            )
    with pytest.raises(ConnectorCapabilityEnablementError, match="invalid"):
        await service.create(
            actor=capability_enabler(),
            source_validation_id=validation.validation_id,
            source_validation_digest="f" * 64,
            package_digest=validation.package_digest,
            capability_profile_id=profile.profile_id,
            capability_profile_digest=profile.canonical_digest,
            enablement_policy_id=policy.policy_id,
            enablement_policy_digest=policy.canonical_digest,
            purpose="Reject mismatched immutable capability enablement lineage.",
            acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority=True,
            idempotency_key="capability-invalid-001",
            correlation_id="cor_invalid",
        )


@pytest.mark.asyncio
async def test_enablement_rejects_capability_subset_not_equal_to_manifest() -> None:
    (
        _,
        validation_service,
        _,
        _,
        _,
        _,
        _,
        validation,
        profile,
        policy,
    ) = await capability_enablement_fixture()
    altered = replace(profile.capabilities[0], required_permission="permission.attacker-read")
    unsafe = replace(
        profile,
        capabilities=(altered, *profile.capabilities[1:]),
        canonical_digest="0" * 64,
    )
    unsafe = replace(unsafe, canonical_digest=_signed_snapshot(unsafe))
    service = ConnectorCapabilityEnablementService(
        repository=InMemoryConnectorCapabilityEnablementRepository(),
        validation_source=validation_service,
        profile_source=InMemoryConnectorCapabilityProfileSource((unsafe,)),
        policy_source=InMemoryConnectorCapabilityEnablementPolicySource((policy,)),
        audit_sink=CollectingAuditSink(),
        environment_id=validation.environment_id,
        clock=lambda: validation.validated_at,
    )
    with pytest.raises(ConnectorCapabilityEnablementError, match="invalid"):
        await enable_capabilities(service, validation, unsafe, policy)


@pytest.mark.asyncio
async def test_enablement_requires_audit_before_persistence() -> None:
    service, _, _, _, _, _, _, validation, profile, policy = await capability_enablement_fixture(
        audit_sink=FailingAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await enable_capabilities(service, validation, profile, policy)
    assert (
        await service.repository.get_by_validation(source_validation_id=validation.validation_id)
        is None
    )


@pytest.mark.asyncio
async def test_enablement_postgres_payload_round_trip_is_bounded() -> None:
    service, _, _, _, _, _, _, validation, profile, policy = await capability_enablement_fixture()
    record = await enable_capabilities(service, validation, profile, policy)
    raw = ConnectorCapabilityEnablementService._normalize(asdict(record))
    assert isinstance(raw, dict)
    restored = PostgreSQLConnectorCapabilityEnablementRepository._to_domain(raw)
    assert restored == record
    rendered = repr(raw).lower()
    for hidden in ("endpoint_url", "secret_reference_id", "password", "command", "parameters"):
        assert hidden not in rendered


def test_enablement_api_rejects_caller_capabilities_and_minimizes_response(
    tmp_path: Path,
) -> None:
    (
        service,
        validation_service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        validation,
        profile,
        policy,
    ) = asyncio.run(capability_enablement_fixture())
    subject = capability_enabler()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-capability-enablement-input.v1",
        "source_validation_id": validation.validation_id,
        "source_validation_digest": validation.canonical_digest,
        "package_digest": validation.package_digest,
        "capability_profile_id": profile.profile_id,
        "capability_profile_digest": profile.canonical_digest,
        "enablement_policy_id": policy.policy_id,
        "enablement_policy_digest": policy.canonical_digest,
        "purpose": "Enable exact governed read-only capabilities without runtime authority.",
        "acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority": True,
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
            configuration_validation_service=validation_service,
            capability_enablement_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/capability-enablements"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "cap-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "capabilities": ["attacker.write"]},
            headers={
                "Idempotency-Key": "cap-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "cap-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        enablement_id = created.json()["data"]["enablement_id"]
        read = client.get(f"{endpoint}/{enablement_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["connector_enabled"] is True and data["runtime_trust_granted"] is False
    rendered = created.text.lower()
    for hidden in (
        "endpoint_url",
        "secret_reference_id",
        "secret_store_profile_id",
        "request_fingerprint",
        "idempotency_key",
        "password",
        "command",
        "parameters",
    ):
        assert hidden not in rendered
