from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import (
    FailSecondAuditSink,
    activate_runtime,
    runtime_activation_fixture,
    runtime_activation_operator,
)
from test_secret_brokerage import RuntimeFixture

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.target_session_memory import (
    InMemoryConnectorTargetSessionPolicySource,
    InMemoryConnectorTargetSessionProfileSource,
    InMemoryConnectorTargetSessionRepository,
)
from atlas.modules.connectors.adapters.target_session_postgres import (
    PostgreSQLConnectorTargetSessionRepository,
)
from atlas.modules.connectors.adapters.target_session_synthetic import (
    SyntheticConnectorTargetSessionAdapter,
)
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
)
from atlas.modules.connectors.application.secret_brokerage import ConnectorSecretBrokerageService
from atlas.modules.connectors.application.target_session import (
    ConnectorTargetSessionService,
    _signed_snapshot,
    build_connector_target_session_profile,
    build_development_connector_target_session_policy,
)
from atlas.modules.connectors.application.target_session_ports import ConnectorTargetSessionError
from atlas.modules.connectors.domain.runtime_activation import ConnectorRuntimeActivationRecord
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetSessionPolicySnapshot,
    ConnectorTargetSessionProfileSnapshot,
    ConnectorTargetSessionVerificationRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

ACKNOWLEDGEMENT_FIELD = "acknowledged_bounded_session_grants_no_invocation_execution_or_deployment"


def target_session_operator(
    subject_id: str = "subject.connector-independent-target-session-operator",
) -> AuthenticatedSubject:
    return runtime_activation_operator(subject_id)


def development_target_session_operator(
    subject_id: str = "subject.connector-independent-target-session-operator",
) -> AuthenticatedSubject:
    return replace(
        target_session_operator(subject_id),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )


async def target_session_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    ConnectorTargetSessionService,
    ConnectorRuntimeActivationService,
    ConnectorSecretBrokerageService,
    RuntimeFixture,
    ConnectorRuntimeActivationRecord,
    ConnectorSecretBrokerageAuthorizationRecord,
    ConnectorRuntimeTrustGrantRecord,
    ConnectorTargetSessionProfileSnapshot,
    ConnectorTargetSessionPolicySnapshot,
    SyntheticConnectorTargetSessionAdapter,
]:
    (
        runtime_service,
        brokerage_service,
        runtime_fixture,
        runtime_trust,
        brokerage,
        runtime_profile,
        runtime_policy,
        _,
    ) = await runtime_activation_fixture()
    activation = await activate_runtime(runtime_service, brokerage, runtime_profile, runtime_policy)
    profile = build_connector_target_session_profile(
        activation=activation,
        brokerage=brokerage,
        runtime_trust=runtime_trust,
        issued_at=activation.healthy_at,
        expires_at=activation.healthy_at + timedelta(days=10),
    )
    policy = build_development_connector_target_session_policy(
        organization_id=activation.organization_id,
        environment_id=activation.environment_id,
        issued_at=activation.healthy_at - timedelta(hours=1),
        expires_at=activation.healthy_at + timedelta(days=10),
    )
    if policy.required_assurance_level is not required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_snapshot(policy))
    adapter = SyntheticConnectorTargetSessionAdapter(clock=lambda: activation.healthy_at)
    service = ConnectorTargetSessionService(
        repository=InMemoryConnectorTargetSessionRepository(),
        source=runtime_service,
        profile_source=InMemoryConnectorTargetSessionProfileSource((profile,)),
        policy_source=InMemoryConnectorTargetSessionPolicySource((policy,)),
        adapter=adapter,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=activation.environment_id,
        clock=lambda: activation.healthy_at,
    )
    return (
        service,
        runtime_service,
        brokerage_service,
        runtime_fixture,
        activation,
        brokerage,
        runtime_trust,
        profile,
        policy,
        adapter,
    )


async def verify_target_session(
    service: ConnectorTargetSessionService,
    activation: ConnectorRuntimeActivationRecord,
    profile: ConnectorTargetSessionProfileSnapshot,
    policy: ConnectorTargetSessionPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "target-session-001",
) -> ConnectorTargetSessionVerificationRecord:
    return await service.create(
        actor=actor or target_session_operator(),
        source_runtime_activation_id=activation.activation_id,
        source_runtime_activation_digest=activation.canonical_digest,
        package_digest=activation.package_digest,
        session_profile_id=profile.profile_id,
        session_profile_digest=profile.canonical_digest,
        session_policy_id=policy.policy_id,
        session_policy_digest=policy.canonical_digest,
        purpose="Verify one bounded read-only target session and close every ephemeral handle.",
        bounded_session_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_target_session",
    )


@pytest.mark.asyncio
async def test_target_session_is_bounded_read_only_closed_and_idempotent() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture(
        audit_sink=audit
    )
    record = await verify_target_session(service, activation, profile, policy)
    repeated = await verify_target_session(service, activation, profile, policy)

    assert record.instance_state == "enabled_target_session_verified"
    assert record.target_connection_authorized and record.target_connectivity_verified
    assert record.target_identity_verified and record.read_only_session_verified
    assert record.target_session_established and record.target_session_closed
    assert record.delivery_channel_closed and record.lease_revocation_confirmed
    assert record.eligible_for_capability_invocation_governance
    assert not record.target_connected and not record.capability_invoked
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and repeated.verification_id == record.verification_id
    assert [item.result_code for item in audit.records] == [
        "connector_target_session_requested",
        "connector_target_session_completed",
    ]


@pytest.mark.asyncio
async def test_target_session_accepts_development_identity_under_default_policy() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()

    record = await verify_target_session(
        service,
        activation,
        profile,
        policy,
        actor=development_target_session_operator(),
    )

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.verified_by == "subject.connector-independent-target-session-operator"
    assert record.target_session_closed and not record.target_connected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "required_assurance_level",
    (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED),
)
async def test_target_session_enforces_explicit_step_up_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(ConnectorTargetSessionError, match="target_session_invalid"):
        await verify_target_session(
            service,
            activation,
            profile,
            policy,
            actor=development_target_session_operator(),
        )


@pytest.mark.asyncio
async def test_target_session_denies_non_human_identity() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    actor = replace(development_target_session_operator(), kind=SubjectKind.SERVICE)

    with pytest.raises(ConnectorTargetSessionError, match="target_session_human_required"):
        await verify_target_session(service, activation, profile, policy, actor=actor)


@pytest.mark.asyncio
async def test_target_session_rejects_actor_reuse_and_altered_network_policy() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    with pytest.raises(ConnectorTargetSessionError, match="separation_required"):
        await verify_target_session(
            service,
            activation,
            profile,
            policy,
            actor=target_session_operator(activation.activated_by),
        )

    unsafe = replace(profile, network_path_policy_digest="f" * 64, canonical_digest="0" * 64)
    unsafe = replace(unsafe, canonical_digest=_signed_snapshot(unsafe))
    unsafe_service = ConnectorTargetSessionService(
        repository=InMemoryConnectorTargetSessionRepository(),
        source=service._source,
        profile_source=InMemoryConnectorTargetSessionProfileSource((unsafe,)),
        policy_source=InMemoryConnectorTargetSessionPolicySource((policy,)),
        adapter=SyntheticConnectorTargetSessionAdapter(clock=service._clock),
        audit_sink=CollectingAuditSink(),
        environment_id=activation.environment_id,
        clock=service._clock,
    )
    with pytest.raises(ConnectorTargetSessionError, match="invalid"):
        await verify_target_session(
            unsafe_service, activation, unsafe, policy, key="unsafe-session-001"
        )


@pytest.mark.asyncio
async def test_target_session_completion_audit_failure_compensates() -> None:
    service, _, _, _, activation, _, _, profile, policy, adapter = await target_session_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(ConnectorTargetSessionError, match="failed"):
        await verify_target_session(service, activation, profile, policy)
    seed = ConnectorTargetSessionService._digest(
        [activation.activation_id, profile.profile_id, profile.canonical_digest]
    )
    verification_id = f"connector-target-session-verification.{seed[:24]}"
    assert verification_id in adapter.compensated
    assert await service.repository.get(verification_id=verification_id) is None


@pytest.mark.asyncio
async def test_target_session_postgres_round_trip_excludes_sensitive_material() -> None:
    service, _, _, _, activation, _, _, profile, policy, _ = await target_session_fixture()
    record = await verify_target_session(service, activation, profile, policy)
    raw = ConnectorTargetSessionService._normalize(asdict(record))
    assert isinstance(raw, dict)
    restored = PostgreSQLConnectorTargetSessionRepository._to_domain(raw)
    assert restored == record
    rendered = repr(raw).lower()
    for hidden in (
        "target_address",
        "target_endpoint",
        "target_port",
        "credential_profile_id",
        "secret_reference_id",
        "secret_store_profile_id",
        "broker_id",
        "lease_handle",
        "session_handle",
        "certificate_body",
        "raw_vendor_output",
        "transcript",
        "password",
        "access_token",
    ):
        assert hidden not in rendered


def test_target_session_api_is_csrf_protected_forbids_coordinates_and_is_minimized(
    tmp_path: Path,
) -> None:
    (
        service,
        runtime_service,
        brokerage_service,
        runtime_fixture,
        activation,
        _,
        _,
        profile,
        policy,
        _,
    ) = asyncio.run(target_session_fixture())
    (
        runtime_trust_service,
        enablement_service,
        validation_service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        *_rest,
    ) = runtime_fixture
    subject = development_target_session_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.connector-target-session-input.v1",
        "source_runtime_activation_id": activation.activation_id,
        "source_runtime_activation_digest": activation.canonical_digest,
        "package_digest": activation.package_digest,
        "session_profile_id": profile.profile_id,
        "session_profile_digest": profile.canonical_digest,
        "session_policy_id": policy.policy_id,
        "session_policy_digest": policy.canonical_digest,
        "purpose": "Verify one bounded read-only target session and close every ephemeral handle.",
        ACKNOWLEDGEMENT_FIELD: True,
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
            capability_enablement_service=enablement_service,
            runtime_trust_service=runtime_trust_service,
            secret_brokerage_service=brokerage_service,
            runtime_activation_service=runtime_service,
            target_session_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/target-session-verifications"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "session-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "target_address": "192.0.2.10"},
            headers={
                "Idempotency-Key": "session-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "session-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        verification_id = created.json()["data"]["verification_id"]
        read = client.get(f"{endpoint}/{verification_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["target_connectivity_verified"] is True
    assert data["target_session_closed"] is True
    assert data["target_connected"] is False
    rendered = created.text.lower()
    for hidden in (
        "target_address",
        "target_endpoint",
        "target_port",
        "credential_profile_id",
        "secret_reference_id",
        "secret_store_profile_id",
        "broker_id",
        "lease_handle",
        "session_handle",
        "certificate_body",
        "raw_vendor_output",
        "transcript",
        "request_fingerprint",
        "idempotency_key",
        "password",
        "access_token",
        "command",
    ):
        assert hidden not in rendered
