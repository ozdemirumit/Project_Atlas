from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Table, UniqueConstraint
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_configuration_validation import (
    configuration_validation_fixture,
    validate_configuration,
)
from test_instance_creation import instance_operator
from test_package_acquisition import CollectingAuditSink, FailingAuditSink

from atlas.api.app import create_app
from atlas.core.persistence.models import ConnectorCapabilityEnablementModel
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
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
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


class TrackingCapabilityProfileSource(InMemoryConnectorCapabilityProfileSource):
    def __init__(self, profiles: tuple[ConnectorCapabilityProfileSnapshot, ...]) -> None:
        super().__init__(profiles)
        self.scoped_lookups = 0

    async def get_by_id_in_scope(
        self,
        *,
        profile_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityProfileSnapshot | None:
        self.scoped_lookups += 1
        return await super().get_by_id_in_scope(
            profile_id=profile_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )


class TrackingCapabilityPolicySource(InMemoryConnectorCapabilityEnablementPolicySource):
    def __init__(self, policies: tuple[ConnectorCapabilityEnablementPolicySnapshot, ...]) -> None:
        super().__init__(policies)
        self.scoped_lookups = 0

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorCapabilityEnablementPolicySnapshot | None:
        self.scoped_lookups += 1
        return await super().get_by_id_in_scope(
            policy_id=policy_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )


class FixedCapabilityValidationSource:
    def __init__(
        self,
        validation: ConnectorConfigurationValidationRecord,
        registration: ConnectorPackageRegistrationRecord,
        source_actors: frozenset[str],
    ) -> None:
        self._validation = validation
        self._registration = registration
        self._source_actors = source_actors

    async def capability_enablement_source(
        self, *, validation_id: str
    ) -> tuple[
        ConnectorConfigurationValidationRecord,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]:
        if validation_id != self._validation.validation_id:
            raise ConnectorCapabilityEnablementError("capability_enablement_source_not_found")
        return self._validation, self._registration, self._source_actors

    async def capability_enablement_source_in_scope(
        self,
        *,
        validation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[
        ConnectorConfigurationValidationRecord,
        ConnectorPackageRegistrationRecord,
        frozenset[str],
    ]:
        if (
            validation_id != self._validation.validation_id
            or organization_id != self._validation.organization_id
            or environment_id != self._validation.environment_id
        ):
            raise ConnectorCapabilityEnablementError("capability_enablement_source_not_found")
        return self._validation, self._registration, self._source_actors


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
async def test_enablement_rejects_capability_profile_tuple_not_declared_by_manifest() -> None:
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
async def test_enablement_accepts_exact_signed_c0_c1_manifest_subset() -> None:
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
    _, registration, source_actors = await validation_service.capability_enablement_source(
        validation_id=validation.validation_id
    )
    second_capability = replace(
        registration.manifest.capabilities[0],
        capability_id="storage.events.read",
        required_permission="connectors.storage.events.read",
    )
    expanded_manifest = replace(
        registration.manifest,
        capabilities=(*registration.manifest.capabilities, second_capability),
        manifest_digest="e" * 64,
    )
    expanded_registration = replace(registration, manifest=expanded_manifest)
    expanded_validation = replace(
        validation,
        manifest_digest=expanded_manifest.manifest_digest,
    )
    subset = replace(
        profile,
        manifest_digest=expanded_manifest.manifest_digest,
        capabilities=(profile.capabilities[0],),
        canonical_digest="0" * 64,
    )
    subset = replace(subset, canonical_digest=_signed_snapshot(subset))
    service = ConnectorCapabilityEnablementService(
        repository=InMemoryConnectorCapabilityEnablementRepository(),
        validation_source=FixedCapabilityValidationSource(
            expanded_validation,
            expanded_registration,
            source_actors,
        ),
        profile_source=InMemoryConnectorCapabilityProfileSource((subset,)),
        policy_source=InMemoryConnectorCapabilityEnablementPolicySource((policy,)),
        audit_sink=CollectingAuditSink(),
        environment_id=validation.environment_id,
        clock=lambda: validation.validated_at,
    )

    record = await enable_capabilities(service, expanded_validation, subset, policy)

    assert len(expanded_registration.manifest.capabilities) == 2
    assert record.capabilities == subset.capabilities


@pytest.mark.asyncio
async def test_enablement_rejects_future_configuration_validation() -> None:
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
    now = validation.validated_at - timedelta(minutes=1)
    current_profile = replace(
        profile,
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=10),
        canonical_digest="0" * 64,
    )
    current_profile = replace(
        current_profile,
        canonical_digest=_signed_snapshot(current_profile),
    )
    service = ConnectorCapabilityEnablementService(
        repository=InMemoryConnectorCapabilityEnablementRepository(),
        validation_source=validation_service,
        profile_source=InMemoryConnectorCapabilityProfileSource((current_profile,)),
        policy_source=InMemoryConnectorCapabilityEnablementPolicySource((policy,)),
        audit_sink=CollectingAuditSink(),
        environment_id=validation.environment_id,
        clock=lambda: now,
    )

    assert (
        await service.list_options(
            actor=capability_enabler(),
            source_validation_id=validation.validation_id,
            correlation_id="cor_future_validation_options",
        )
        == ()
    )
    with pytest.raises(ConnectorCapabilityEnablementError, match="invalid"):
        await enable_capabilities(service, validation, current_profile, policy)


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


@pytest.mark.asyncio
async def test_enablement_uniqueness_is_scoped_in_memory_and_postgres_contract() -> None:
    service, _, _, _, _, _, _, validation, profile, policy = await capability_enablement_fixture()
    first = await enable_capabilities(service, validation, profile, policy)
    second = replace(
        first,
        enablement_id="connector-capability-enablement.other-scope",
        organization_id="organization.other",
        environment_id="environment.other",
        canonical_digest="0" * 64,
    )
    second = replace(
        second,
        canonical_digest=service._digest(service._record_payload(second)),
    )
    repository = InMemoryConnectorCapabilityEnablementRepository()

    assert await repository.add(first)
    assert await repository.add(second)
    assert (
        await repository.get_by_validation_in_scope(
            source_validation_id=first.source_validation_id,
            organization_id=first.organization_id,
            environment_id=first.environment_id,
        )
        == first
    )
    assert (
        await repository.get_by_create_key_in_scope(
            enabled_by=second.enabled_by,
            idempotency_key=second.idempotency_key,
            organization_id=second.organization_id,
            environment_id=second.environment_id,
        )
        == second
    )

    table = cast(Table, ConnectorCapabilityEnablementModel.__table__)
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert constraints["uq_connector_capability_enablements_validation"] == (
        "organization_id",
        "environment_id",
        "source_validation_id",
    )
    assert constraints["uq_connector_capability_enablements_actor_idempotency"] == (
        "organization_id",
        "environment_id",
        "enabled_by",
        "idempotency_key",
    )


@pytest.mark.asyncio
async def test_enablement_options_are_server_selected_and_inventory_is_reloadable() -> None:
    service, _, _, _, _, _, _, validation, profile, policy = await capability_enablement_fixture()
    actor = capability_enabler()

    options = await service.list_options(
        actor=actor,
        source_validation_id=validation.validation_id,
        correlation_id="cor_capability_options",
    )

    assert len(options) == 1
    option = options[0]
    assert option.source_validation_id == validation.validation_id
    assert option.source_validation_digest == validation.canonical_digest
    assert option.package_digest == validation.package_digest
    assert option.capability_profile_id == profile.profile_id
    assert option.capability_profile_digest == profile.canonical_digest
    assert option.capabilities == profile.capabilities
    assert option.enablement_policy_id == policy.policy_id
    assert option.enablement_policy_digest == policy.canonical_digest
    assert option.resulting_instance_state == "enabled_capabilities_governed"
    for hidden in (
        "target_profile_id",
        "target_product",
        "credential_profile_id",
        "secret_reference_id",
        "command",
        "parameters",
        "signature",
        "request_fingerprint",
        "idempotency_key",
        "probe_runner_id",
        "runtime_profile_id",
    ):
        assert hidden not in asdict(option)

    record = await enable_capabilities(service, validation, profile, policy, actor=actor)
    assert await service.list_enablements(
        actor=actor,
        source_validation_id=None,
        correlation_id="cor_capability_inventory",
    ) == (record,)
    assert await service.list_enablements(
        actor=actor,
        source_validation_id=validation.validation_id,
        correlation_id="cor_capability_inventory_filtered",
    ) == (record,)
    assert (
        await service.list_options(
            actor=actor,
            source_validation_id=validation.validation_id,
            correlation_id="cor_capability_options_after_create",
        )
        == ()
    )


@pytest.mark.asyncio
async def test_enablement_inventory_filters_foreign_validation_without_discovery() -> None:
    service, _, _, _, _, _, _, validation, profile, policy = await capability_enablement_fixture()
    actor = capability_enabler()
    record = await enable_capabilities(service, validation, profile, policy, actor=actor)
    foreign = replace(
        record,
        enablement_id="connector-capability-enablement.foreign",
        source_validation_id="connector-configuration-validation.foreign",
        organization_id="organization.foreign",
        enabled_by="subject.foreign-enabler",
        idempotency_key="capability-foreign-001",
        canonical_digest="0" * 64,
    )
    foreign = replace(
        foreign,
        canonical_digest=service._digest(service._record_payload(foreign)),
    )
    assert await service.repository.add(foreign)

    assert await service.list_enablements(
        actor=actor,
        source_validation_id=None,
        correlation_id="cor_capability_scoped_inventory",
    ) == (record,)
    foreign_result = await service.list_enablements(
        actor=actor,
        source_validation_id=foreign.source_validation_id,
        correlation_id="cor_capability_foreign_filter",
    )
    missing_result = await service.list_enablements(
        actor=actor,
        source_validation_id="connector-configuration-validation.missing",
        correlation_id="cor_capability_missing_filter",
    )
    assert foreign_result == missing_result == ()


@pytest.mark.asyncio
async def test_enablement_create_checks_validation_scope_before_profile_policy_lookup() -> None:
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
    foreign = replace(
        validation,
        validation_id="connector-configuration-validation.foreign",
        organization_id="organization.foreign",
        canonical_digest="0" * 64,
    )
    foreign = replace(
        foreign,
        canonical_digest=validation_service._digest(validation_service._record_payload(foreign)),
    )
    assert await validation_service.repository.add(foreign)
    profile_source = TrackingCapabilityProfileSource((profile,))
    policy_source = TrackingCapabilityPolicySource((policy,))
    guarded_service = ConnectorCapabilityEnablementService(
        repository=InMemoryConnectorCapabilityEnablementRepository(),
        validation_source=validation_service,
        profile_source=profile_source,
        policy_source=policy_source,
        audit_sink=CollectingAuditSink(),
        environment_id=validation.environment_id,
        clock=lambda: validation.validated_at,
    )

    with pytest.raises(ConnectorCapabilityEnablementError) as foreign_error:
        await enable_capabilities(guarded_service, foreign, profile, policy)
    with pytest.raises(ConnectorCapabilityEnablementError) as missing_error:
        await guarded_service.create(
            actor=capability_enabler(),
            source_validation_id="connector-configuration-validation.missing",
            source_validation_digest=validation.canonical_digest,
            package_digest=validation.package_digest,
            capability_profile_id=profile.profile_id,
            capability_profile_digest=profile.canonical_digest,
            enablement_policy_id=policy.policy_id,
            enablement_policy_digest=policy.canonical_digest,
            purpose="Reject undiscoverable connector capability enablement sources.",
            acknowledged_enablement_grants_no_secret_runtime_execution_or_deployment_authority=True,
            idempotency_key="capability-missing-001",
            correlation_id="cor_capability_missing",
        )
    with pytest.raises(ConnectorCapabilityEnablementError) as foreign_options_error:
        await guarded_service.list_options(
            actor=capability_enabler(),
            source_validation_id=foreign.validation_id,
            correlation_id="cor_capability_foreign_options",
        )
    with pytest.raises(ConnectorCapabilityEnablementError) as missing_options_error:
        await guarded_service.list_options(
            actor=capability_enabler(),
            source_validation_id="connector-configuration-validation.missing",
            correlation_id="cor_capability_missing_options",
        )

    assert str(foreign_error.value) == str(missing_error.value)
    assert str(foreign_error.value) == "capability_enablement_source_not_found"
    assert str(foreign_options_error.value) == str(missing_options_error.value)
    assert str(foreign_options_error.value) == "capability_enablement_source_not_found"
    assert profile_source.scoped_lookups == policy_source.scoped_lookups == 0


@pytest.mark.asyncio
async def test_enablement_options_fail_closed_for_freshness_lineage_separation_and_assurance() -> (
    None
):
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
    stale = replace(
        profile,
        issued_at=validation.validated_at - timedelta(days=20),
        expires_at=validation.validated_at - timedelta(days=10),
        canonical_digest="0" * 64,
    )
    stale = replace(stale, canonical_digest=_signed_snapshot(stale))
    wrong_lineage = replace(
        profile,
        package_digest="f" * 64,
        canonical_digest="0" * 64,
    )
    wrong_lineage = replace(wrong_lineage, canonical_digest=_signed_snapshot(wrong_lineage))
    weak_actor = replace(
        capability_enabler(),
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
        (stale, policy, capability_enabler()),
        (wrong_lineage, policy, capability_enabler()),
        (profile, policy, capability_enabler(profile.signed_by)),
        (profile, strong_policy, weak_actor),
    )
    for candidate_profile, candidate_policy, actor in cases:
        guarded_service = ConnectorCapabilityEnablementService(
            repository=InMemoryConnectorCapabilityEnablementRepository(),
            validation_source=validation_service,
            profile_source=InMemoryConnectorCapabilityProfileSource((candidate_profile,)),
            policy_source=InMemoryConnectorCapabilityEnablementPolicySource((candidate_policy,)),
            audit_sink=CollectingAuditSink(),
            environment_id=validation.environment_id,
            clock=lambda: validation.validated_at,
        )
        assert (
            await guarded_service.list_options(
                actor=actor,
                source_validation_id=validation.validation_id,
                correlation_id="cor_capability_guarded_options",
            )
            == ()
        )


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
        endpoint = "/api/v1/connectors/capability-enablements"
        unauthenticated_inventory = client.get(endpoint)
        login_response = login(client)
        inventory_before = client.get(
            endpoint, params={"source_validation_id": validation.validation_id}
        )
        options_before = client.get(
            f"{endpoint}/options",
            params={"source_validation_id": validation.validation_id},
        )
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
        inventory_after = client.get(
            endpoint, params={"source_validation_id": validation.validation_id}
        )
        options_after = client.get(
            f"{endpoint}/options",
            params={"source_validation_id": validation.validation_id},
        )
        missing_inventory = client.get(
            endpoint,
            params={"source_validation_id": "connector-configuration-validation.missing"},
        )

    assert unauthenticated_inventory.status_code == 401
    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert inventory_before.status_code == options_before.status_code == 200
    assert inventory_before.json()["data"] == []
    assert len(options_before.json()["data"]) == 1
    option = options_before.json()["data"][0]
    assert option["source_validation_id"] == validation.validation_id
    assert option["source_validation_digest"] == validation.canonical_digest
    assert option["capability_profile_id"] == profile.profile_id
    assert option["capability_profile_digest"] == profile.canonical_digest
    assert option["enablement_policy_id"] == policy.policy_id
    assert option["enablement_policy_digest"] == policy.canonical_digest
    assert option["resulting_instance_state"] == "enabled_capabilities_governed"
    assert option["resulting_capability_governance_applied"] is True
    assert option["connector_enabled"] is True
    assert option["eligible_for_runtime_trust"] is True
    assert option["credentials_resolved"] is False
    assert option["runtime_trust_granted"] is False
    assert option["execution_authorized"] is False
    assert option["deployment_approved"] is False
    assert option["infrastructure_mutation_performed"] is False
    assert len(inventory_after.json()["data"]) == 1
    inventory = inventory_after.json()["data"][0]
    assert inventory["enablement_id"] == enablement_id
    assert inventory["source_validation_id"] == validation.validation_id
    assert inventory["capability_governance_applied"] is True
    assert inventory["connector_enabled"] is True
    assert inventory["eligible_for_runtime_trust"] is True
    assert inventory["runtime_trust_granted"] is False
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
    assert data["connector_enabled"] is True and data["runtime_trust_granted"] is False
    rendered = (
        f"{created.text}\n{read.text}\n{inventory_after.text}\n{options_before.text}"
    ).lower()
    for hidden in (
        "endpoint_url",
        "target_profile_id",
        "target_product",
        "credential_profile_id",
        "secret_reference_id",
        "secret_store_profile_id",
        "request_fingerprint",
        "idempotency_key",
        "password",
        "command",
        "parameters",
        "signature",
        "probe_runner_id",
        "runtime_profile_id",
    ):
        assert hidden not in rendered
