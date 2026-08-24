from __future__ import annotations

import asyncio
import os
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import FailSecondAuditSink
from test_secret_brokerage import RuntimeFixture
from test_target_session import (
    development_target_session_operator,
    target_session_fixture,
    target_session_operator,
    verify_target_session,
)

from atlas.api.app import create_app
from atlas.core.persistence.models import ConnectorInvocationAuthorizationModel
from atlas.modules.connectors.adapters.invocation_authorization_memory import (
    DevelopmentConnectorInvocationEvidenceStore,
    DevelopmentConnectorInvocationInputEnvelopeSource,
    DevelopmentConnectorInvocationProfileSource,
    InMemoryConnectorInvocationAuthorizationPolicySource,
    InMemoryConnectorInvocationAuthorizationRepository,
    InMemoryConnectorInvocationInputEnvelopeSource,
    InMemoryConnectorInvocationProfileSource,
)
from atlas.modules.connectors.adapters.invocation_authorization_postgres import (
    PostgreSQLConnectorInvocationAuthorizationRepository,
)
from atlas.modules.connectors.application.invocation_authorization import (
    ConnectorInvocationAuthorizationService,
    _signed_snapshot,
    build_connector_invocation_input_envelope,
    build_connector_invocation_profile,
    build_development_connector_invocation_authorization_policy,
)
from atlas.modules.connectors.application.invocation_authorization_ports import (
    ConnectorInvocationAuthorizationError,
)
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
)
from atlas.modules.connectors.application.secret_brokerage import (
    ConnectorSecretBrokerageService,
)
from atlas.modules.connectors.application.target_session import ConnectorTargetSessionService
from atlas.modules.connectors.domain.invocation_authorization import (
    ConnectorInvocationAuthorizationPolicySnapshot,
    ConnectorInvocationAuthorizationRecord,
    ConnectorInvocationInputEnvelopeSnapshot,
    ConnectorInvocationProfileSnapshot,
)
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionVerificationRecord,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind

ACKNOWLEDGEMENT_FIELD = (
    "acknowledged_single_use_authorization_grants_no_invocation_schedule_execution_or_deployment"
)


class RecordingPermissionAuthorizer:
    def __init__(self, *, deny: bool = False) -> None:
        self.deny = deny
        self.calls: list[tuple[str, str, str]] = []

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        permission_id: str,
        capability_id: str,
        capability_class: str,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None:
        del actor, organization_id, environment_id, correlation_id
        self.calls.append((permission_id, capability_id, capability_class))
        if self.deny:
            raise ConnectorInvocationAuthorizationError(
                "invocation_authorization_capability_permission_denied"
            )


async def invocation_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    permission_authorizer: RecordingPermissionAuthorizer | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    ConnectorInvocationAuthorizationService,
    ConnectorTargetSessionService,
    ConnectorRuntimeActivationService,
    ConnectorSecretBrokerageService,
    RuntimeFixture,
    ConnectorTargetSessionVerificationRecord,
    ConnectorInvocationProfileSnapshot,
    ConnectorInvocationInputEnvelopeSnapshot,
    ConnectorInvocationAuthorizationPolicySnapshot,
    RecordingPermissionAuthorizer,
]:
    (
        target_service,
        runtime_service,
        brokerage_service,
        runtime_fixture,
        activation,
        _,
        _,
        target_profile,
        target_policy,
        _,
    ) = await target_session_fixture()
    target_session = await verify_target_session(
        target_service, activation, target_profile, target_policy
    )
    _, enablement, _ = await target_service.capability_invocation_authorization_source(
        verification_id=target_session.verification_id,
        organization_id=target_session.organization_id,
        environment_id=target_session.environment_id,
    )
    capability = enablement.capabilities[0]
    profile = build_connector_invocation_profile(
        source=target_session,
        capability=capability,
        issued_at=target_session.verified_at,
        expires_at=target_session.verified_at + timedelta(hours=4),
    )
    envelope = build_connector_invocation_input_envelope(
        profile=profile,
        issued_at=target_session.verified_at,
        expires_at=target_session.verified_at + timedelta(hours=2),
    )
    policy = build_development_connector_invocation_authorization_policy(
        organization_id=target_session.organization_id,
        environment_id=target_session.environment_id,
        issued_at=target_session.verified_at - timedelta(hours=1),
        expires_at=target_session.verified_at + timedelta(days=1),
    )
    if policy.required_assurance_level is not required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_snapshot(policy))
    authorizer = permission_authorizer or RecordingPermissionAuthorizer()
    service = ConnectorInvocationAuthorizationService(
        repository=InMemoryConnectorInvocationAuthorizationRepository(),
        source=target_service,
        profile_source=InMemoryConnectorInvocationProfileSource((profile,)),
        envelope_source=InMemoryConnectorInvocationInputEnvelopeSource((envelope,)),
        policy_source=InMemoryConnectorInvocationAuthorizationPolicySource((policy,)),
        permission_authorizer=authorizer,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=target_session.environment_id,
        clock=lambda: target_session.verified_at,
    )
    return (
        service,
        target_service,
        runtime_service,
        brokerage_service,
        runtime_fixture,
        target_session,
        profile,
        envelope,
        policy,
        authorizer,
    )


async def authorize_invocation(
    service: ConnectorInvocationAuthorizationService,
    source: ConnectorTargetSessionVerificationRecord,
    profile: ConnectorInvocationProfileSnapshot,
    envelope: ConnectorInvocationInputEnvelopeSnapshot,
    policy: ConnectorInvocationAuthorizationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "invocation-authorization-001",
) -> ConnectorInvocationAuthorizationRecord:
    return await service.create(
        actor=actor
        or target_session_operator("subject.connector-independent-invocation-authorizer"),
        source_target_session_verification_id=source.verification_id,
        source_target_session_digest=source.canonical_digest,
        package_digest=source.package_digest,
        capability_id=profile.capability_id,
        invocation_profile_id=profile.profile_id,
        invocation_profile_digest=profile.canonical_digest,
        input_envelope_id=envelope.envelope_id,
        input_envelope_digest=envelope.canonical_digest,
        authorization_policy_id=policy.policy_id,
        authorization_policy_digest=policy.canonical_digest,
        purpose="Authorize one bounded read-only capability invocation without invoking it.",
        single_use_boundary_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_invocation_authorization",
    )


@pytest.mark.asyncio
async def test_invocation_authorization_is_single_use_bounded_and_idempotent() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, _, source, profile, envelope, policy, authorizer = await invocation_fixture(
        audit_sink=audit
    )
    actor = target_session_operator("subject.connector-independent-invocation-authorizer")
    record = await authorize_invocation(service, source, profile, envelope, policy, actor=actor)
    repeated = await authorize_invocation(service, source, profile, envelope, policy, actor=actor)
    with pytest.raises(ConnectorInvocationAuthorizationError, match="source_not_found"):
        await authorize_invocation(
            service,
            source,
            profile,
            envelope,
            policy,
            actor=replace(actor, organization_id="organization.other"),
        )

    assert record.instance_state == "enabled_capability_invocation_governed"
    assert record.capability_invocation_authorized
    assert record.eligible_for_bounded_capability_invocation
    assert record.single_use and not record.renewable and not record.consumed
    assert not record.target_connected and not record.capability_invoked
    assert not record.scheduled and not record.result_received
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and repeated.authorization_id == record.authorization_id
    assert authorizer.calls == [
        (profile.required_permission, profile.capability_id, profile.capability_class)
    ]
    assert [item.result_code for item in audit.records] == [
        "connector_invocation_authorization_requested",
        "connector_invocation_authorization_completed",
    ]


@pytest.mark.asyncio
async def test_invocation_authorization_accepts_development_identity_under_default_policy() -> None:
    service, _, _, _, _, source, profile, envelope, policy, _ = await invocation_fixture()
    actor = development_target_session_operator(
        "subject.connector-independent-invocation-authorizer"
    )

    record = await authorize_invocation(service, source, profile, envelope, policy, actor=actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.authorized_by == actor.subject_id
    assert record.single_use and not record.consumed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "required_assurance_level",
    (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED),
)
async def test_invocation_authorization_enforces_explicit_step_up_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, _, _, _, source, profile, envelope, policy, authorizer = await invocation_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(
        ConnectorInvocationAuthorizationError, match="invocation_authorization_invalid"
    ):
        await authorize_invocation(
            service,
            source,
            profile,
            envelope,
            policy,
            actor=development_target_session_operator(
                "subject.connector-independent-invocation-authorizer"
            ),
        )

    assert authorizer.calls == []


@pytest.mark.asyncio
async def test_invocation_authorization_denies_non_human_identity() -> None:
    service, _, _, _, _, source, profile, envelope, policy, authorizer = await invocation_fixture()
    actor = replace(
        development_target_session_operator("subject.connector-independent-invocation-authorizer"),
        kind=SubjectKind.SERVICE,
    )

    with pytest.raises(
        ConnectorInvocationAuthorizationError,
        match="invocation_authorization_human_required",
    ):
        await authorize_invocation(service, source, profile, envelope, policy, actor=actor)

    assert authorizer.calls == []


@pytest.mark.asyncio
async def test_invocation_authorization_rejects_actor_reuse_and_altered_envelope() -> None:
    service, _, _, _, _, source, profile, envelope, policy, _ = await invocation_fixture()
    with pytest.raises(ConnectorInvocationAuthorizationError, match="separation_required"):
        await authorize_invocation(
            service,
            source,
            profile,
            envelope,
            policy,
            actor=target_session_operator(source.verified_by),
        )

    altered = replace(envelope, normalized_input_digest="f" * 64)
    altered_service = ConnectorInvocationAuthorizationService(
        repository=InMemoryConnectorInvocationAuthorizationRepository(),
        source=service._source,
        profile_source=InMemoryConnectorInvocationProfileSource((profile,)),
        envelope_source=InMemoryConnectorInvocationInputEnvelopeSource((altered,)),
        policy_source=InMemoryConnectorInvocationAuthorizationPolicySource((policy,)),
        permission_authorizer=RecordingPermissionAuthorizer(),
        audit_sink=CollectingAuditSink(),
        environment_id=source.environment_id,
        clock=service._clock,
    )
    with pytest.raises(ConnectorInvocationAuthorizationError, match="integrity_failed"):
        await authorize_invocation(
            altered_service, source, profile, altered, policy, key="altered-envelope-001"
        )


@pytest.mark.asyncio
async def test_invocation_authorization_permission_and_audit_fail_closed() -> None:
    denied_service, _, _, _, _, source, profile, envelope, policy, _ = await invocation_fixture(
        permission_authorizer=RecordingPermissionAuthorizer(deny=True)
    )
    with pytest.raises(ConnectorInvocationAuthorizationError, match="permission_denied"):
        await authorize_invocation(denied_service, source, profile, envelope, policy)
    assert (
        await denied_service.repository.get_by_target_session_in_scope(
            source_target_session_verification_id=source.verification_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
        )
        is None
    )

    failed_service, _, _, _, _, source, profile, envelope, policy, _ = await invocation_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(ConnectorInvocationAuthorizationError, match="audit_failed"):
        await authorize_invocation(failed_service, source, profile, envelope, policy)
    assert (
        await failed_service.repository.get_by_target_session_in_scope(
            source_target_session_verification_id=source.verification_id,
            organization_id=source.organization_id,
            environment_id=source.environment_id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_invocation_authorization_postgres_round_trip_excludes_sensitive_material() -> None:
    service, _, _, _, _, source, profile, envelope, policy, _ = await invocation_fixture()
    record = await authorize_invocation(service, source, profile, envelope, policy)
    raw = ConnectorInvocationAuthorizationService._normalize(asdict(record))
    assert isinstance(raw, dict)
    restored = PostgreSQLConnectorInvocationAuthorizationRepository._to_domain(raw)
    assert restored == record
    stored = PostgreSQLConnectorInvocationAuthorizationRepository._storage_payload(record)
    assert "replay_digest" not in stored
    assert "idempotency_digest" not in stored
    assert "reused" not in stored
    rendered = repr(raw).lower()
    for hidden in (
        "raw_input",
        "input_values",
        "target_address",
        "target_endpoint",
        "target_port",
        "credential_profile_id",
        "secret_reference_id",
        "lease_handle",
        "session_handle",
        "raw_vendor_output",
        "command",
        "password",
        "access_token",
    ):
        assert hidden not in rendered


@pytest.mark.asyncio
async def test_invocation_authorization_options_and_inventory_are_tenant_scoped() -> None:
    service, _, _, _, _, source, profile, envelope, policy, authorizer = await invocation_fixture()
    actor = target_session_operator("subject.connector-independent-invocation-authorizer")

    options = await service.list_options(
        actor=actor,
        source_target_session_verification_id=source.verification_id,
        correlation_id="cor_invocation_options",
    )

    assert len(options) == 1
    option = options[0]
    assert option.source_target_session_digest == source.canonical_digest
    assert option.capability_id == profile.capability_id
    assert option.invocation_profile_digest == profile.canonical_digest
    assert option.input_envelope_digest == envelope.canonical_digest
    assert option.authorization_policy_digest == policy.canonical_digest
    assert authorizer.calls == [
        (profile.required_permission, profile.capability_id, profile.capability_class)
    ]

    record = await authorize_invocation(service, source, profile, envelope, policy, actor=actor)
    inventory = await service.list_authorizations(
        actor=actor,
        source_target_session_verification_id=source.verification_id,
        correlation_id="cor_invocation_inventory",
    )
    assert inventory == (record,)
    assert (
        await service.list_options(
            actor=actor,
            source_target_session_verification_id=source.verification_id,
            correlation_id="cor_invocation_options_existing",
        )
        == ()
    )

    foreign_actor = replace(actor, organization_id="organization.other")
    assert (
        await service.list_authorizations(
            actor=foreign_actor,
            source_target_session_verification_id=source.verification_id,
            correlation_id="cor_invocation_inventory_foreign",
        )
        == ()
    )
    with pytest.raises(ConnectorInvocationAuthorizationError, match="source_not_found"):
        await service.list_options(
            actor=foreign_actor,
            source_target_session_verification_id=source.verification_id,
            correlation_id="cor_invocation_options_foreign",
        )


@pytest.mark.asyncio
async def test_development_invocation_evidence_is_server_prepared_and_restart_stable() -> None:
    service, _, _, _, _, source, _, _, policy, _ = await invocation_fixture()
    actor = target_session_operator("subject.connector-independent-invocation-authorizer")
    repository = InMemoryConnectorInvocationAuthorizationRepository()

    def development_service() -> ConnectorInvocationAuthorizationService:
        store = DevelopmentConnectorInvocationEvidenceStore()
        return ConnectorInvocationAuthorizationService(
            repository=repository,
            source=service._source,
            profile_source=DevelopmentConnectorInvocationProfileSource(store),
            envelope_source=DevelopmentConnectorInvocationInputEnvelopeSource(store),
            policy_source=InMemoryConnectorInvocationAuthorizationPolicySource((policy,)),
            evidence_preparer=store,
            permission_authorizer=RecordingPermissionAuthorizer(),
            audit_sink=CollectingAuditSink(),
            environment_id=source.environment_id,
            clock=service._clock,
        )

    first_service = development_service()
    options = await first_service.list_options(
        actor=actor,
        source_target_session_verification_id=source.verification_id,
        correlation_id="cor_invocation_development_options",
    )
    assert len(options) == 1
    option = options[0]
    record = await first_service.create(
        actor=actor,
        source_target_session_verification_id=option.source_target_session_verification_id,
        source_target_session_digest=option.source_target_session_digest,
        package_digest=option.package_digest,
        capability_id=option.capability_id,
        invocation_profile_id=option.invocation_profile_id,
        invocation_profile_digest=option.invocation_profile_digest,
        input_envelope_id=option.input_envelope_id,
        input_envelope_digest=option.input_envelope_digest,
        authorization_policy_id=option.authorization_policy_id,
        authorization_policy_digest=option.authorization_policy_digest,
        purpose="Authorize one server-prepared bounded read-only invocation without invoking it.",
        single_use_boundary_acknowledged=True,
        idempotency_key="development-server-option-001",
        correlation_id="cor_invocation_development_create",
    )

    restarted = development_service()
    assert await restarted.list_authorizations(
        actor=actor,
        source_target_session_verification_id=source.verification_id,
        correlation_id="cor_invocation_development_restart",
    ) == (record,)


@pytest.mark.asyncio
async def test_invocation_authorization_cross_service_race_returns_one_record() -> None:
    service, _, _, _, _, source, profile, envelope, policy, _ = await invocation_fixture()
    repository = InMemoryConnectorInvocationAuthorizationRepository()

    def clone() -> ConnectorInvocationAuthorizationService:
        return ConnectorInvocationAuthorizationService(
            repository=repository,
            source=service._source,
            profile_source=InMemoryConnectorInvocationProfileSource((profile,)),
            envelope_source=InMemoryConnectorInvocationInputEnvelopeSource((envelope,)),
            policy_source=InMemoryConnectorInvocationAuthorizationPolicySource((policy,)),
            permission_authorizer=RecordingPermissionAuthorizer(),
            audit_sink=CollectingAuditSink(),
            environment_id=source.environment_id,
            clock=service._clock,
        )

    first, second = await asyncio.gather(
        authorize_invocation(
            clone(), source, profile, envelope, policy, key="cross-service-invoke-001"
        ),
        authorize_invocation(
            clone(), source, profile, envelope, policy, key="cross-service-invoke-001"
        ),
    )

    assert first.authorization_id == second.authorization_id
    assert first.reused is not second.reused
    assert (
        len(
            await repository.list_scope(
                organization_id=source.organization_id,
                environment_id=source.environment_id,
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_invocation_authorization_postgres_is_scoped_and_minimized() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    service, _, _, _, _, source, profile, envelope, policy, _ = await invocation_fixture()
    record = await authorize_invocation(service, source, profile, envelope, policy)
    engine = create_async_engine(database_url)
    repository = PostgreSQLConnectorInvocationAuthorizationRepository(engine)
    try:
        async with engine.begin() as connection:
            await connection.execute(delete(ConnectorInvocationAuthorizationModel))
        assert await repository.add(record)
        restored = await repository.get_in_scope(
            authorization_id=record.authorization_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        assert restored == record
        assert (
            await repository.get_in_scope(
                authorization_id=record.authorization_id,
                organization_id="organization.other",
                environment_id=record.environment_id,
            )
            is None
        )
        assert await repository.list_scope(
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        ) == (record,)
        foreign = replace(
            record,
            authorization_id="connector-invocation-authorization.foreign-tenant",
            organization_id="organization.other",
            replay_digest="2" * 64,
            idempotency_digest="3" * 64,
            canonical_digest="0" * 64,
        )
        foreign = replace(
            foreign,
            canonical_digest=service._digest(service._record_payload(foreign)),
        )
        assert await repository.add(foreign)
        assert await repository.list_scope(
            organization_id=foreign.organization_id,
            environment_id=foreign.environment_id,
        ) == (foreign,)
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    select(
                        ConnectorInvocationAuthorizationModel.idempotency_digest,
                        ConnectorInvocationAuthorizationModel.replay_digest,
                        ConnectorInvocationAuthorizationModel.payload,
                    ).where(
                        ConnectorInvocationAuthorizationModel.authorization_id
                        == record.authorization_id
                    )
                )
            ).one()
            assert len(row.idempotency_digest) == 64
            assert len(row.replay_digest) == 64
            for hidden in (
                "request_fingerprint",
                "idempotency_key",
                "idempotency_digest",
                "replay_digest",
                "reused",
            ):
                assert hidden not in row.payload
    finally:
        async with engine.begin() as connection:
            await connection.execute(delete(ConnectorInvocationAuthorizationModel))
        await repository.close()


def test_invocation_authorization_api_is_csrf_protected_and_minimized(tmp_path: Path) -> None:
    (
        service,
        target_service,
        runtime_service,
        brokerage_service,
        runtime_fixture,
        source,
        profile,
        envelope,
        policy,
        _,
    ) = asyncio.run(invocation_fixture())
    (
        runtime_trust_service,
        enablement_service,
        validation_service,
        assignment_service,
        target_configuration_service,
        instance_service,
        installation_service,
        registration_service,
        *_rest,
    ) = runtime_fixture
    subject = development_target_session_operator(
        "subject.connector-independent-invocation-authorizer"
    )
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.connector-invocation-authorization-input.v1",
        "source_target_session_verification_id": source.verification_id,
        "source_target_session_digest": source.canonical_digest,
        "package_digest": source.package_digest,
        "capability_id": profile.capability_id,
        "invocation_profile_id": profile.profile_id,
        "invocation_profile_digest": profile.canonical_digest,
        "input_envelope_id": envelope.envelope_id,
        "input_envelope_digest": envelope.canonical_digest,
        "authorization_policy_id": policy.policy_id,
        "authorization_policy_digest": policy.canonical_digest,
        "purpose": "Authorize one bounded read-only capability invocation without invoking it.",
        ACKNOWLEDGEMENT_FIELD: True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_registration_service=registration_service,
            package_installation_service=installation_service,
            connector_instance_creation_service=instance_service,
            target_configuration_service=target_configuration_service,
            credential_assignment_service=assignment_service,
            configuration_validation_service=validation_service,
            capability_enablement_service=enablement_service,
            runtime_trust_service=runtime_trust_service,
            secret_brokerage_service=brokerage_service,
            runtime_activation_service=runtime_service,
            target_session_service=target_service,
            invocation_authorization_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/invocation-authorizations"
        options = client.get(
            f"{endpoint}/options",
            params={"source_target_session_verification_id": source.verification_id},
        )
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "invoke-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "raw_parameters": {"command": "show all"}},
            headers={
                "Idempotency-Key": "invoke-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "invoke-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        authorization_id = created.json()["data"]["authorization_id"]
        read = client.get(f"{endpoint}/{authorization_id}")
        inventory = client.get(
            endpoint,
            params={"source_target_session_verification_id": source.verification_id},
        )

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert options.status_code == 200 and len(options.json()["data"]) == 1
    assert read.status_code == 200
    assert inventory.status_code == 200 and inventory.json()["data"] == [read.json()["data"]]
    assert (
        created.headers["Cache-Control"]
        == read.headers["Cache-Control"]
        == inventory.headers["Cache-Control"]
        == options.headers["Cache-Control"]
        == "no-store"
    )
    data = created.json()["data"]
    assert data["capability_permission_verified"] is True
    assert data["single_use"] is True and data["capability_invoked"] is False
    rendered = created.text.lower()
    for hidden in (
        "raw_parameters",
        "input_values",
        "target_address",
        "credential_profile_id",
        "secret_reference_id",
        "lease_handle",
        "session_handle",
        "raw_vendor_output",
        "request_fingerprint",
        "idempotency_key",
        "password",
        "access_token",
        "command",
        "authorized_by",
        "purpose",
        "organization_id",
        "environment_id",
        "instance_id",
        "required_permission",
        "invocation_profile_id",
        "input_envelope_id",
        "authorization_policy_id",
    ):
        assert hidden not in rendered
