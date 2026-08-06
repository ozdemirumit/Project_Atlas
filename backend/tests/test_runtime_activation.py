from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink
from test_secret_brokerage import (
    RuntimeFixture,
    authorize_secret_brokerage,
    secret_brokerage_authorizer,
    secret_brokerage_fixture,
)

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.modules.connectors.adapters.runtime_activation_memory import (
    InMemoryConnectorRuntimeActivationPolicySource,
    InMemoryConnectorRuntimeActivationProfileSource,
    InMemoryConnectorRuntimeActivationRepository,
)
from atlas.modules.connectors.adapters.runtime_activation_postgres import (
    PostgreSQLConnectorRuntimeActivationRepository,
)
from atlas.modules.connectors.adapters.runtime_activation_synthetic import (
    SyntheticConnectorRuntimeActivator,
)
from atlas.modules.connectors.application.runtime_activation import (
    ConnectorRuntimeActivationService,
    _signed_snapshot,
    build_connector_runtime_activation_profile,
    build_development_connector_runtime_activation_policy,
)
from atlas.modules.connectors.application.runtime_activation_ports import (
    ConnectorRuntimeActivationError,
)
from atlas.modules.connectors.application.secret_brokerage import ConnectorSecretBrokerageService
from atlas.modules.connectors.domain.runtime_activation import (
    ConnectorRuntimeActivationPolicySnapshot,
    ConnectorRuntimeActivationProfileSnapshot,
    ConnectorRuntimeActivationRecord,
)
from atlas.modules.connectors.domain.runtime_trust import ConnectorRuntimeTrustGrantRecord
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

ACKNOWLEDGEMENT_FIELD = (
    "acknowledged_activation_grants_no_target_connection_invocation_execution_or_deployment"
)


class FailSecondAuditSink:
    def __init__(self) -> None:
        self.calls = 0

    async def record(self, event: AuditRecord) -> None:
        del event
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("audit unavailable")


def runtime_activation_operator(
    subject_id: str = "subject.connector-independent-runtime-activation-operator",
) -> AuthenticatedSubject:
    return secret_brokerage_authorizer(subject_id)


async def runtime_activation_fixture(
    *, audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None
) -> tuple[
    ConnectorRuntimeActivationService,
    ConnectorSecretBrokerageService,
    RuntimeFixture,
    ConnectorRuntimeTrustGrantRecord,
    ConnectorSecretBrokerageAuthorizationRecord,
    ConnectorRuntimeActivationProfileSnapshot,
    ConnectorRuntimeActivationPolicySnapshot,
    SyntheticConnectorRuntimeActivator,
]:
    (
        brokerage_service,
        runtime_fixture,
        runtime_trust,
        brokerage_profile,
        brokerage_policy,
    ) = await secret_brokerage_fixture()
    brokerage = await authorize_secret_brokerage(
        brokerage_service, runtime_trust, brokerage_profile, brokerage_policy
    )
    profile = build_connector_runtime_activation_profile(
        source=brokerage,
        runtime_trust=runtime_trust,
        issued_at=runtime_trust.granted_at,
        expires_at=runtime_trust.granted_at + timedelta(days=10),
    )
    policy = build_development_connector_runtime_activation_policy(
        organization_id=runtime_trust.organization_id,
        environment_id=runtime_trust.environment_id,
        issued_at=runtime_trust.granted_at - timedelta(hours=1),
        expires_at=runtime_trust.granted_at + timedelta(days=10),
    )
    activator = SyntheticConnectorRuntimeActivator(clock=lambda: runtime_trust.granted_at)
    service = ConnectorRuntimeActivationService(
        repository=InMemoryConnectorRuntimeActivationRepository(),
        source=brokerage_service,
        profile_source=InMemoryConnectorRuntimeActivationProfileSource((profile,)),
        policy_source=InMemoryConnectorRuntimeActivationPolicySource((policy,)),
        activator=activator,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=runtime_trust.environment_id,
        clock=lambda: runtime_trust.granted_at,
    )
    return (
        service,
        brokerage_service,
        runtime_fixture,
        runtime_trust,
        brokerage,
        profile,
        policy,
        activator,
    )


async def activate_runtime(
    service: ConnectorRuntimeActivationService,
    brokerage: ConnectorSecretBrokerageAuthorizationRecord,
    profile: ConnectorRuntimeActivationProfileSnapshot,
    policy: ConnectorRuntimeActivationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "runtime-activation-001",
) -> ConnectorRuntimeActivationRecord:
    return await service.create(
        actor=actor or runtime_activation_operator(),
        source_brokerage_authorization_id=brokerage.authorization_id,
        source_brokerage_authorization_digest=brokerage.canonical_digest,
        package_digest=brokerage.package_digest,
        activation_profile_id=profile.profile_id,
        activation_profile_digest=profile.canonical_digest,
        activation_policy_id=policy.policy_id,
        activation_policy_digest=policy.canonical_digest,
        purpose="Activate the exact isolated connector runtime and verify local health only.",
        activation_boundary_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_runtime_activation",
    )


@pytest.mark.asyncio
async def test_runtime_activation_proves_health_without_target_authority() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture(
        audit_sink=audit
    )
    record = await activate_runtime(service, brokerage, profile, policy)
    repeated = await activate_runtime(service, brokerage, profile, policy)

    assert record.instance_state == "enabled_runtime_healthy"
    assert record.secret_lease_issued and record.credentials_resolved
    assert record.runner_started and record.package_loaded and record.runtime_health_verified
    assert record.delivery_channel_closed and record.lease_revocation_confirmed
    assert record.eligible_for_target_session_authorization
    assert not record.target_connected and not record.target_connection_authorized
    assert not record.capability_invocation_authorized and not record.capability_invoked
    assert not record.execution_authorized and not record.deployment_approved
    assert repeated.reused and repeated.activation_id == record.activation_id
    assert [item.result_code for item in audit.records] == [
        "connector_runtime_activation_requested",
        "connector_runtime_activation_completed",
    ]


@pytest.mark.asyncio
async def test_runtime_activation_rejects_actor_reuse_and_altered_profile() -> None:
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture()
    with pytest.raises(ConnectorRuntimeActivationError, match="separation_required"):
        await activate_runtime(
            service,
            brokerage,
            profile,
            policy,
            actor=runtime_activation_operator(brokerage.authorized_by),
        )

    unsafe = replace(profile, egress_policy_digest="f" * 64, canonical_digest="0" * 64)
    unsafe = replace(unsafe, canonical_digest=_signed_snapshot(unsafe))
    unsafe_service = ConnectorRuntimeActivationService(
        repository=InMemoryConnectorRuntimeActivationRepository(),
        source=service._source,
        profile_source=InMemoryConnectorRuntimeActivationProfileSource((unsafe,)),
        policy_source=InMemoryConnectorRuntimeActivationPolicySource((policy,)),
        activator=SyntheticConnectorRuntimeActivator(clock=service._clock),
        audit_sink=CollectingAuditSink(),
        environment_id=brokerage.environment_id,
        clock=service._clock,
    )
    with pytest.raises(ConnectorRuntimeActivationError, match="invalid"):
        await activate_runtime(unsafe_service, brokerage, unsafe, policy, key="unsafe-runtime-001")


@pytest.mark.asyncio
async def test_completion_audit_failure_compensates_and_does_not_persist() -> None:
    service, _, _, _, brokerage, profile, policy, activator = await runtime_activation_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(ConnectorRuntimeActivationError, match="failed"):
        await activate_runtime(service, brokerage, profile, policy)
    expected_id = (
        "connector-runtime-activation."
        + ConnectorRuntimeActivationService._digest(
            [brokerage.authorization_id, profile.profile_id, profile.canonical_digest]
        )[:24]
    )
    assert expected_id in activator.compensated
    assert await service.repository.get(activation_id=expected_id) is None


@pytest.mark.asyncio
async def test_runtime_activation_postgres_round_trip_excludes_sensitive_material() -> None:
    service, _, _, _, brokerage, profile, policy, _ = await runtime_activation_fixture()
    record = await activate_runtime(service, brokerage, profile, policy)
    raw = ConnectorRuntimeActivationService._normalize(asdict(record))
    assert isinstance(raw, dict)
    restored = PostgreSQLConnectorRuntimeActivationRepository._to_domain(raw)
    assert restored == record
    rendered = repr(raw).lower()
    for hidden in (
        "secret_reference_id",
        "secret_store_profile_id",
        "secret_value",
        "password",
        "lease_handle",
        "access_token",
        "bearer_token",
        "raw_health_output",
        "process_output",
    ):
        assert hidden not in rendered


def test_runtime_activation_api_is_csrf_protected_and_minimized(tmp_path: Path) -> None:
    (
        service,
        brokerage_service,
        runtime_fixture,
        _,
        brokerage,
        profile,
        policy,
        _,
    ) = asyncio.run(runtime_activation_fixture())
    (
        runtime_service,
        enablement_service,
        validation_service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        *_rest,
    ) = runtime_fixture
    subject = runtime_activation_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.connector-runtime-activation-input.v1",
        "source_brokerage_authorization_id": brokerage.authorization_id,
        "source_brokerage_authorization_digest": brokerage.canonical_digest,
        "package_digest": brokerage.package_digest,
        "activation_profile_id": profile.profile_id,
        "activation_profile_digest": profile.canonical_digest,
        "activation_policy_id": policy.policy_id,
        "activation_policy_digest": policy.canonical_digest,
        "purpose": "Activate the exact isolated connector runtime and verify local health only.",
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
            runtime_trust_service=runtime_service,
            secret_brokerage_service=brokerage_service,
            runtime_activation_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/runtime-activations"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "runtime-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "lease_handle": "attacker-controlled"},
            headers={
                "Idempotency-Key": "runtime-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "runtime-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        activation_id = created.json()["data"]["activation_id"]
        read = client.get(f"{endpoint}/{activation_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["runtime_health_verified"] is True
    assert data["target_connection_authorized"] is False
    rendered = created.text.lower()
    for hidden in (
        "credential_profile_id",
        "secret_reference_id",
        "secret_store_profile_id",
        "broker_id",
        "lease_handle",
        "request_fingerprint",
        "idempotency_key",
        "password",
        "access_token",
        "bearer_token",
        "raw_health_output",
        "process_output",
        "command",
    ):
        assert hidden not in rendered
