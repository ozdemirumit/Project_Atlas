from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_runtime_trust import (
    grant_runtime_trust,
    runtime_trust_fixture,
    runtime_trust_granter,
)

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.secret_brokerage_memory import (
    InMemoryConnectorSecretBrokeragePolicySource,
    InMemoryConnectorSecretBrokerageProfileSource,
    InMemoryConnectorSecretBrokerageRepository,
)
from atlas.modules.connectors.adapters.secret_brokerage_postgres import (
    PostgreSQLConnectorSecretBrokerageRepository,
)
from atlas.modules.connectors.application.capability_enablement import (
    ConnectorCapabilityEnablementService,
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
from atlas.modules.connectors.application.runtime_trust import ConnectorRuntimeTrustService
from atlas.modules.connectors.application.secret_brokerage import (
    ConnectorSecretBrokerageService,
    _signed_snapshot,
    build_connector_secret_brokerage_profile,
    build_development_connector_secret_brokerage_policy,
)
from atlas.modules.connectors.application.secret_brokerage_ports import (
    ConnectorSecretBrokerageError,
)
from atlas.modules.connectors.application.target_configuration import (
    ConnectorTargetConfigurationService,
)
from atlas.modules.connectors.domain.capability_enablement import (
    ConnectorCapabilityEnablementRecord,
)
from atlas.modules.connectors.domain.runtime_trust import (
    ConnectorRuntimeTrustGrantRecord,
    ConnectorRuntimeTrustPolicySnapshot,
    ConnectorRuntimeTrustProfileSnapshot,
)
from atlas.modules.connectors.domain.secret_brokerage import (
    ConnectorSecretBrokerageAuthorizationRecord,
    ConnectorSecretBrokeragePolicySnapshot,
    ConnectorSecretBrokerageProfileSnapshot,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

ACKNOWLEDGEMENT_FIELD = (
    "acknowledged_authorization_grants_no_lease_secret_runtime_target_execution_or_deployment"
)

type RuntimeFixture = tuple[
    ConnectorRuntimeTrustService,
    ConnectorCapabilityEnablementService,
    ConnectorConfigurationValidationService,
    ConnectorCredentialAssignmentService,
    ConnectorTargetConfigurationService,
    ConnectorInstanceCreationService,
    PackageInstallationService,
    PackageRegistrationService,
    ConnectorCapabilityEnablementRecord,
    ConnectorRuntimeTrustProfileSnapshot,
    ConnectorRuntimeTrustPolicySnapshot,
]


def secret_brokerage_authorizer(
    subject_id: str = "subject.connector-independent-secret-brokerage-authorizer",
) -> AuthenticatedSubject:
    return runtime_trust_granter(subject_id)


async def secret_brokerage_fixture(
    *, audit_sink: CollectingAuditSink | FailingAuditSink | None = None
) -> tuple[
    ConnectorSecretBrokerageService,
    RuntimeFixture,
    ConnectorRuntimeTrustGrantRecord,
    ConnectorSecretBrokerageProfileSnapshot,
    ConnectorSecretBrokeragePolicySnapshot,
]:
    runtime_fixture = await runtime_trust_fixture()
    runtime_service = runtime_fixture[0]
    assignment_service = runtime_fixture[3]
    enablement = runtime_fixture[8]
    runtime_profile = runtime_fixture[9]
    runtime_policy = runtime_fixture[10]
    runtime_trust = await grant_runtime_trust(
        runtime_service, enablement, runtime_profile, runtime_policy
    )
    _, credential_profile, _ = await assignment_service.secret_brokerage_source(
        credential_profile_id=runtime_trust.credential_profile_id,
        instance_id=runtime_trust.instance_id,
    )
    profile = build_connector_secret_brokerage_profile(
        runtime_trust=runtime_trust,
        credential_profile=credential_profile,
        issued_at=runtime_trust.granted_at,
        expires_at=runtime_trust.granted_at + timedelta(days=10),
    )
    policy = build_development_connector_secret_brokerage_policy(
        organization_id=runtime_trust.organization_id,
        environment_id=runtime_trust.environment_id,
        issued_at=runtime_trust.granted_at - timedelta(hours=1),
        expires_at=runtime_trust.granted_at + timedelta(days=10),
    )
    service = ConnectorSecretBrokerageService(
        repository=InMemoryConnectorSecretBrokerageRepository(),
        runtime_trust_source=runtime_service,
        credential_source=assignment_service,
        profile_source=InMemoryConnectorSecretBrokerageProfileSource((profile,)),
        policy_source=InMemoryConnectorSecretBrokeragePolicySource((policy,)),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=runtime_trust.environment_id,
        clock=lambda: runtime_trust.granted_at,
    )
    return service, runtime_fixture, runtime_trust, profile, policy


async def authorize_secret_brokerage(
    service: ConnectorSecretBrokerageService,
    runtime_trust: ConnectorRuntimeTrustGrantRecord,
    profile: ConnectorSecretBrokerageProfileSnapshot,
    policy: ConnectorSecretBrokeragePolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "secret-brokerage-001",
) -> ConnectorSecretBrokerageAuthorizationRecord:
    return await service.create(
        actor=actor or secret_brokerage_authorizer(),
        source_runtime_trust_grant_id=runtime_trust.grant_id,
        source_runtime_trust_digest=runtime_trust.canonical_digest,
        package_digest=runtime_trust.package_digest,
        brokerage_profile_id=profile.profile_id,
        brokerage_profile_digest=profile.canonical_digest,
        brokerage_policy_id=policy.policy_id,
        brokerage_policy_digest=policy.canonical_digest,
        purpose="Authorize exact future memory-only secret brokerage without issuing a lease.",
        authorization_only_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_secret_brokerage",
    )


@pytest.mark.asyncio
async def test_secret_brokerage_authorizes_only_future_runtime_activation() -> None:
    audit = CollectingAuditSink()
    service, _, runtime_trust, profile, policy = await secret_brokerage_fixture(audit_sink=audit)
    record = await authorize_secret_brokerage(service, runtime_trust, profile, policy)
    repeated = await authorize_secret_brokerage(service, runtime_trust, profile, policy)

    assert record.secret_brokerage_governed and record.credential_resolution_authorized
    assert record.eligible_for_runtime_activation
    assert record.instance_state == "enabled_secret_brokerage_governed"
    assert repeated.reused and repeated.authorization_id == record.authorization_id
    assert not record.secret_lease_issued and not record.credentials_resolved
    assert not record.runner_started and not record.package_loaded
    assert not record.target_connection_authorized and not record.capability_invocation_authorized
    assert not record.execution_authorized and not record.deployment_approved
    assert [item.result_code for item in audit.records] == [
        "connector_secret_brokerage_requested",
        "connector_secret_brokerage_completed",
    ]


@pytest.mark.asyncio
async def test_secret_brokerage_enforces_complete_actor_separation() -> None:
    service, runtime_fixture, runtime_trust, profile, policy = await secret_brokerage_fixture()
    runtime_service = runtime_fixture[0]
    assignment_service = runtime_fixture[3]
    _, runtime_actors = await runtime_service.secret_brokerage_source(
        grant_id=runtime_trust.grant_id
    )
    _, _, credential_actors = await assignment_service.secret_brokerage_source(
        credential_profile_id=runtime_trust.credential_profile_id,
        instance_id=runtime_trust.instance_id,
    )
    for subject_id in (
        *sorted(runtime_actors | credential_actors),
        profile.signed_by,
        policy.signed_by,
    ):
        with pytest.raises(ConnectorSecretBrokerageError, match="separation_required"):
            await authorize_secret_brokerage(
                service,
                runtime_trust,
                profile,
                policy,
                actor=secret_brokerage_authorizer(subject_id),
                key=f"secret-brokerage-{subject_id}",
            )


@pytest.mark.asyncio
async def test_secret_brokerage_rejects_altered_signed_delivery_policy() -> None:
    _, runtime_fixture, runtime_trust, profile, policy = await secret_brokerage_fixture()
    unsafe = replace(
        profile,
        delivery_policy_id="secret-delivery-policy.unapproved",
        canonical_digest="0" * 64,
    )
    unsafe = replace(unsafe, canonical_digest=_signed_snapshot(unsafe))
    service = ConnectorSecretBrokerageService(
        repository=InMemoryConnectorSecretBrokerageRepository(),
        runtime_trust_source=runtime_fixture[0],
        credential_source=runtime_fixture[3],
        profile_source=InMemoryConnectorSecretBrokerageProfileSource((unsafe,)),
        policy_source=InMemoryConnectorSecretBrokeragePolicySource((policy,)),
        audit_sink=CollectingAuditSink(),
        environment_id=runtime_trust.environment_id,
        clock=lambda: runtime_trust.granted_at,
    )
    with pytest.raises(ConnectorSecretBrokerageError, match="invalid"):
        await authorize_secret_brokerage(service, runtime_trust, unsafe, policy)


@pytest.mark.asyncio
async def test_secret_brokerage_requires_audit_before_persistence() -> None:
    service, _, runtime_trust, profile, policy = await secret_brokerage_fixture(
        audit_sink=FailingAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await authorize_secret_brokerage(service, runtime_trust, profile, policy)
    assert (
        await service.repository.get_by_runtime_trust(
            source_runtime_trust_grant_id=runtime_trust.grant_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_secret_brokerage_postgres_payload_round_trip_excludes_secret_material() -> None:
    service, _, runtime_trust, profile, policy = await secret_brokerage_fixture()
    record = await authorize_secret_brokerage(service, runtime_trust, profile, policy)
    raw = ConnectorSecretBrokerageService._normalize(asdict(record))
    assert isinstance(raw, dict)
    restored = PostgreSQLConnectorSecretBrokerageRepository._to_domain(raw)
    assert restored == record
    rendered = repr(raw).lower()
    for hidden in (
        "secret_reference_id",
        "secret_value",
        "password",
        "lease_handle",
        "access_token",
        "bearer_token",
    ):
        assert hidden not in rendered


def test_secret_brokerage_api_rejects_caller_controls_and_minimizes_response(
    tmp_path: Path,
) -> None:
    service, runtime_fixture, runtime_trust, profile, policy = asyncio.run(
        secret_brokerage_fixture()
    )
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
    subject = secret_brokerage_authorizer()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.connector-secret-brokerage-input.v1",
        "source_runtime_trust_grant_id": runtime_trust.grant_id,
        "source_runtime_trust_digest": runtime_trust.canonical_digest,
        "package_digest": runtime_trust.package_digest,
        "brokerage_profile_id": profile.profile_id,
        "brokerage_profile_digest": profile.canonical_digest,
        "brokerage_policy_id": policy.policy_id,
        "brokerage_policy_digest": policy.canonical_digest,
        "purpose": "Authorize exact future memory-only secret brokerage without issuing a lease.",
    }
    payload[ACKNOWLEDGEMENT_FIELD] = True
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
            secret_brokerage_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/secret-brokerage-authorizations"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "broker-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "secret_reference_id": "secret.attacker"},
            headers={
                "Idempotency-Key": "broker-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "broker-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        authorization_id = created.json()["data"]["authorization_id"]
        read = client.get(f"{endpoint}/{authorization_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["credential_resolution_authorized"] is True
    assert data["secret_lease_issued"] is False and data["credentials_resolved"] is False
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
        "command",
    ):
        assert hidden not in rendered
