from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import UniqueConstraint
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_credential_assignment import (
    assign_credential,
    credential_assignment_fixture,
)
from test_instance_creation import instance_operator
from test_package_acquisition import CollectingAuditSink, FailingAuditSink

from atlas.api.app import create_app
from atlas.core.persistence.models import ConnectorConfigurationValidationModel
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
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


def configuration_validator(
    subject_id: str = "subject.connector-independent-configuration-validator",
) -> AuthenticatedSubject:
    return instance_operator(subject_id)


class StaticConfigurationAssignmentSource:
    def __init__(
        self,
        assignment: ConnectorCredentialAssignmentRecord,
        registration: ConnectorPackageRegistrationRecord,
        source_actors: frozenset[str],
    ) -> None:
        self._assignment = assignment
        self._registration = registration
        self._source_actors = source_actors

    async def configuration_validation_source(
        self, *, assignment_id: str
    ) -> tuple[
        ConnectorCredentialAssignmentRecord,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]:
        return self._assignment, self._registration, self._source_actors


class TrackingConfigurationEvidenceSource(InMemoryConnectorConfigurationEvidenceSource):
    def __init__(self, snapshots: tuple[ConnectorConfigurationEvidenceSnapshot, ...]) -> None:
        super().__init__(snapshots)
        self.scoped_lookups = 0

    async def get_by_id_in_scope(
        self,
        *,
        evidence_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorConfigurationEvidenceSnapshot | None:
        self.scoped_lookups += 1
        return await super().get_by_id_in_scope(
            evidence_id=evidence_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )


async def configuration_validation_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
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
    if required_assurance_level is not policy.required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_snapshot(policy))
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
async def test_validation_default_policy_accepts_development_password_human() -> None:
    service, _, _, _, _, _, assignment, evidence, policy = await configuration_validation_fixture()
    actor = replace(
        configuration_validator(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    record = await validate_configuration(service, assignment, evidence, policy, actor=actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.validated_by == actor.subject_id
    assert not record.runtime_trust_granted and not record.execution_authorized


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "required_assurance_level",
    (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED),
)
async def test_validation_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, _, _, _, _, assignment, evidence, policy = await configuration_validation_fixture(
        required_assurance_level=required_assurance_level
    )
    actor = replace(
        configuration_validator(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(ConnectorConfigurationValidationError, match="validation_invalid"):
        await validate_configuration(service, assignment, evidence, policy, actor=actor)


@pytest.mark.asyncio
async def test_validation_rejects_non_human_identity() -> None:
    service, _, _, _, _, _, assignment, evidence, policy = await configuration_validation_fixture()
    actor = replace(configuration_validator(), kind=SubjectKind.SERVICE)

    with pytest.raises(
        ConnectorConfigurationValidationError,
        match="configuration_validation_human_required",
    ):
        await validate_configuration(service, assignment, evidence, policy, actor=actor)


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
    _, _, actors = await assignment_service.configuration_validation_source(
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


@pytest.mark.asyncio
async def test_validation_uniqueness_is_scoped_in_memory_and_postgres_contract() -> None:
    service, _, _, _, _, _, assignment, evidence, policy = await configuration_validation_fixture()
    first = await validate_configuration(service, assignment, evidence, policy)
    second = replace(
        first,
        validation_id="connector-configuration-validation.other-scope",
        organization_id="org.other",
        environment_id="env.other",
    )
    repository = InMemoryConnectorConfigurationValidationRepository()

    assert await repository.add(first)
    assert await repository.add(second)
    assert (
        await repository.get_by_assignment_in_scope(
            source_assignment_id=first.source_assignment_id,
            organization_id=first.organization_id,
            environment_id=first.environment_id,
        )
        == first
    )
    assert (
        await repository.get_by_create_key_in_scope(
            validated_by=second.validated_by,
            idempotency_key=second.idempotency_key,
            organization_id=second.organization_id,
            environment_id=second.environment_id,
        )
        == second
    )

    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in ConnectorConfigurationValidationModel.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert constraints["uq_connector_configuration_validations_assignment"] == (
        "organization_id",
        "environment_id",
        "source_assignment_id",
    )
    assert constraints["uq_connector_configuration_validations_actor_idempotency"] == (
        "organization_id",
        "environment_id",
        "validated_by",
        "idempotency_key",
    )


@pytest.mark.asyncio
async def test_validation_options_are_server_selected_and_inventory_is_reloadable() -> None:
    service, _, _, _, _, _, assignment, evidence, policy = await configuration_validation_fixture()
    actor = configuration_validator()

    options = await service.list_options(
        actor=actor,
        source_assignment_id=assignment.assignment_id,
        correlation_id="cor_configuration_options",
    )

    assert len(options) == 1
    option = options[0]
    assert option.source_assignment_id == assignment.assignment_id
    assert option.source_assignment_digest == assignment.canonical_digest
    assert option.package_digest == assignment.package_digest
    assert option.evidence_id == evidence.evidence_id
    assert option.evidence_digest == evidence.canonical_digest
    assert option.validation_policy_id == policy.policy_id
    assert option.validation_policy_digest == policy.canonical_digest
    assert option.authorization_result == "authorization.read-only-confirmed"
    assert option.resulting_instance_state == "disabled_configuration_validated"
    for hidden in (
        "endpoint_url",
        "target_ip",
        "secret_reference_id",
        "secret_store_profile_id",
        "raw_probe_output",
        "signature",
        "request_fingerprint",
        "idempotency_key",
    ):
        assert hidden not in asdict(option)

    record = await validate_configuration(service, assignment, evidence, policy, actor=actor)
    assert await service.list_validations(
        actor=actor,
        source_assignment_id=None,
        correlation_id="cor_configuration_inventory",
    ) == (record,)
    assert await service.list_validations(
        actor=actor,
        source_assignment_id=assignment.assignment_id,
        correlation_id="cor_configuration_inventory_filtered",
    ) == (record,)
    assert (
        await service.list_options(
            actor=actor,
            source_assignment_id=assignment.assignment_id,
            correlation_id="cor_configuration_options_after_create",
        )
        == ()
    )


@pytest.mark.asyncio
async def test_validation_inventory_filters_foreign_assignment_without_discovery() -> None:
    service, _, _, _, _, _, assignment, evidence, policy = await configuration_validation_fixture()
    actor = configuration_validator()
    record = await validate_configuration(service, assignment, evidence, policy, actor=actor)
    foreign = replace(
        record,
        validation_id="connector-configuration-validation.foreign",
        source_assignment_id="connector-credential-assignment.foreign",
        organization_id="organization.foreign",
        validated_by="subject.foreign-validator",
        idempotency_key="configuration-foreign-001",
        canonical_digest="0" * 64,
    )
    foreign = replace(
        foreign,
        canonical_digest=service._digest(service._record_payload(foreign)),
    )
    assert await service.repository.add(foreign)

    assert await service.list_validations(
        actor=actor,
        source_assignment_id=None,
        correlation_id="cor_configuration_scoped_inventory",
    ) == (record,)
    foreign_result = await service.list_validations(
        actor=actor,
        source_assignment_id=foreign.source_assignment_id,
        correlation_id="cor_configuration_foreign_filter",
    )
    missing_result = await service.list_validations(
        actor=actor,
        source_assignment_id="connector-credential-assignment.missing",
        correlation_id="cor_configuration_missing_filter",
    )
    assert foreign_result == missing_result == ()
    assert (
        await service.repository.get_in_scope(
            validation_id=foreign.validation_id,
            organization_id=actor.organization_id,
            environment_id=assignment.environment_id,
        )
        is None
    )
    assert (
        await service.repository.get_by_create_key_in_scope(
            validated_by=foreign.validated_by,
            idempotency_key=foreign.idempotency_key,
            organization_id=actor.organization_id,
            environment_id=assignment.environment_id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_validation_create_checks_assignment_scope_before_evidence_lookup() -> None:
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
    _, registration, source_actors = await assignment_service.configuration_validation_source(
        assignment_id=assignment.assignment_id
    )
    foreign_assignment = replace(assignment, organization_id="organization.foreign")
    evidence_source = TrackingConfigurationEvidenceSource((evidence,))
    foreign_service = ConnectorConfigurationValidationService(
        repository=InMemoryConnectorConfigurationValidationRepository(),
        assignment_source=StaticConfigurationAssignmentSource(
            foreign_assignment, registration, source_actors
        ),
        evidence_source=evidence_source,
        policy_source=InMemoryConnectorConfigurationValidationPolicySource((policy,)),
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.assigned_at,
    )

    with pytest.raises(ConnectorConfigurationValidationError) as foreign_error:
        await validate_configuration(foreign_service, assignment, evidence, policy)
    with pytest.raises(ConnectorConfigurationValidationError) as missing_error:
        await service.create(
            actor=configuration_validator(),
            source_assignment_id="connector-credential-assignment.missing",
            source_assignment_digest=assignment.canonical_digest,
            package_digest=assignment.package_digest,
            evidence_id=evidence.evidence_id,
            evidence_digest=evidence.canonical_digest,
            validation_policy_id=policy.policy_id,
            validation_policy_digest=policy.canonical_digest,
            purpose="Reject undiscoverable connector configuration validation sources.",
            acknowledged_validation_grants_no_secret_network_enablement_or_runtime_authority=True,
            idempotency_key="configuration-missing-001",
            correlation_id="cor_configuration_missing",
        )

    assert str(foreign_error.value) == str(missing_error.value)
    assert str(foreign_error.value) == "configuration_validation_source_not_found"
    assert evidence_source.scoped_lookups == 0


@pytest.mark.asyncio
async def test_validation_options_fail_closed_for_freshness_lineage_separation_and_assurance() -> (
    None
):
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
    stale_at = assignment.assigned_at - timedelta(days=8)
    stale = replace(
        evidence,
        observed_at=stale_at,
        issued_at=stale_at,
        canonical_digest="0" * 64,
    )
    stale = replace(stale, canonical_digest=_signed_snapshot(stale))
    wrong_lineage = replace(
        evidence,
        source_assignment_id="connector-credential-assignment.other",
        canonical_digest="0" * 64,
    )
    wrong_lineage = replace(wrong_lineage, canonical_digest=_signed_snapshot(wrong_lineage))
    weak_actor = replace(
        configuration_validator(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )
    strong_policy = replace(
        policy,
        required_assurance_level=AssuranceLevel.MULTI_FACTOR,
        canonical_digest="0" * 64,
    )
    strong_policy = replace(strong_policy, canonical_digest=_signed_snapshot(strong_policy))

    cases = (
        (stale, policy, configuration_validator()),
        (wrong_lineage, policy, configuration_validator()),
        (evidence, policy, configuration_validator(evidence.signed_by)),
        (evidence, strong_policy, weak_actor),
    )
    for candidate_evidence, candidate_policy, actor in cases:
        guarded_service = ConnectorConfigurationValidationService(
            repository=InMemoryConnectorConfigurationValidationRepository(),
            assignment_source=assignment_service,
            evidence_source=InMemoryConnectorConfigurationEvidenceSource((candidate_evidence,)),
            policy_source=InMemoryConnectorConfigurationValidationPolicySource((candidate_policy,)),
            audit_sink=CollectingAuditSink(),
            environment_id=assignment.environment_id,
            clock=lambda: assignment.assigned_at,
        )
        assert (
            await guarded_service.list_options(
                actor=actor,
                source_assignment_id=assignment.assignment_id,
                correlation_id="cor_configuration_guarded_options",
            )
            == ()
        )

    empty_service = ConnectorConfigurationValidationService(
        repository=InMemoryConnectorConfigurationValidationRepository(),
        assignment_source=assignment_service,
        evidence_source=InMemoryConnectorConfigurationEvidenceSource(()),
        policy_source=InMemoryConnectorConfigurationValidationPolicySource((policy,)),
        audit_sink=CollectingAuditSink(),
        environment_id=assignment.environment_id,
        clock=lambda: assignment.assigned_at,
    )
    assert (
        await empty_service.list_options(
            actor=configuration_validator(),
            source_assignment_id=assignment.assignment_id,
            correlation_id="cor_configuration_empty_options",
        )
        == ()
    )


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
        endpoint = "/api/v1/connectors/configuration-validations"
        unauthenticated_inventory = client.get(endpoint)
        login_response = login(client)
        inventory_before = client.get(
            endpoint, params={"source_assignment_id": assignment.assignment_id}
        )
        options_before = client.get(
            f"{endpoint}/options",
            params={"source_assignment_id": assignment.assignment_id},
        )
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
        inventory_after = client.get(
            endpoint, params={"source_assignment_id": assignment.assignment_id}
        )
        options_after = client.get(
            f"{endpoint}/options",
            params={"source_assignment_id": assignment.assignment_id},
        )
        missing_inventory = client.get(
            endpoint,
            params={"source_assignment_id": "connector-credential-assignment.missing"},
        )

    assert unauthenticated_inventory.status_code == 401
    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert inventory_before.status_code == options_before.status_code == 200
    assert inventory_before.json()["data"] == []
    assert len(options_before.json()["data"]) == 1
    option = options_before.json()["data"][0]
    assert option["source_assignment_id"] == assignment.assignment_id
    assert option["source_assignment_digest"] == assignment.canonical_digest
    assert option["evidence_id"] == evidence.evidence_id
    assert option["evidence_digest"] == evidence.canonical_digest
    assert option["validation_policy_id"] == policy.policy_id
    assert option["validation_policy_digest"] == policy.canonical_digest
    assert option["resulting_instance_state"] == "disabled_configuration_validated"
    assert option["resulting_configuration_validated"] is True
    assert option["credentials_resolved"] is False
    assert option["connector_enabled"] is False
    assert option["runtime_trust_granted"] is False
    assert option["execution_authorized"] is False
    assert option["deployment_approved"] is False
    assert option["infrastructure_mutation_performed"] is False
    assert len(inventory_after.json()["data"]) == 1
    inventory = inventory_after.json()["data"][0]
    assert inventory["validation_id"] == validation_id
    assert inventory["source_assignment_id"] == assignment.assignment_id
    assert inventory["configuration_validated"] is True
    assert inventory["connectivity_evidence_verified"] is True
    assert inventory["connector_enabled"] is False
    assert options_after.json()["data"] == []
    assert missing_inventory.json()["data"] == []
    protected_responses = (
        created,
        read,
        inventory_before,
        options_before,
        inventory_after,
        options_after,
        missing_inventory,
    )
    assert all(item.headers["Cache-Control"] == "no-store" for item in protected_responses)
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
        "signature",
    ):
        assert hidden not in rendered
        assert hidden not in options_before.text.lower()
        assert hidden not in inventory_after.text.lower()
