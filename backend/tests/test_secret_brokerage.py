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
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

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
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
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
    if required_assurance_level is not policy.required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_snapshot(policy))
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
    tenant_scoped_seed = service._digest(
        [
            runtime_trust.organization_id,
            runtime_trust.environment_id,
            runtime_trust.grant_id,
            profile.profile_id,
            profile.canonical_digest,
        ]
    )
    assert record.authorization_id.endswith(tenant_scoped_seed[:24])
    assert not record.secret_lease_issued and not record.credentials_resolved
    assert not record.runner_started and not record.package_loaded
    assert not record.target_connection_authorized and not record.capability_invocation_authorized
    assert not record.execution_authorized and not record.deployment_approved
    assert [item.result_code for item in audit.records] == [
        "connector_secret_brokerage_requested",
        "connector_secret_brokerage_completed",
    ]
    assert all(item.idempotency_key is None for item in audit.records)


@pytest.mark.asyncio
async def test_secret_brokerage_accepts_development_identity_under_default_policy() -> None:
    service, _, runtime_trust, profile, policy = await secret_brokerage_fixture()
    development_actor = replace(
        secret_brokerage_authorizer(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    record = await authorize_secret_brokerage(
        service, runtime_trust, profile, policy, actor=development_actor
    )

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.authorized_by == development_actor.subject_id


@pytest.mark.parametrize(
    "required_assurance_level",
    [AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED],
)
@pytest.mark.asyncio
async def test_secret_brokerage_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, runtime_trust, profile, policy = await secret_brokerage_fixture(
        required_assurance_level=required_assurance_level
    )
    development_actor = replace(
        secret_brokerage_authorizer(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(ConnectorSecretBrokerageError, match="invalid"):
        await authorize_secret_brokerage(
            service, runtime_trust, profile, policy, actor=development_actor
        )


@pytest.mark.asyncio
async def test_secret_brokerage_rejects_non_human_actor() -> None:
    service, _, runtime_trust, profile, policy = await secret_brokerage_fixture()
    service_actor = replace(
        secret_brokerage_authorizer(),
        kind=SubjectKind.SERVICE,
        authentication_method=AuthenticationMethod.WORKLOAD_TOKEN,
    )

    with pytest.raises(ConnectorSecretBrokerageError, match="human_required"):
        await authorize_secret_brokerage(
            service, runtime_trust, profile, policy, actor=service_actor
        )


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


@pytest.mark.asyncio
async def test_secret_brokerage_memory_repository_scopes_uniqueness_and_idempotency() -> None:
    service, _, runtime_trust, profile, policy = await secret_brokerage_fixture()
    record = await authorize_secret_brokerage(service, runtime_trust, profile, policy)
    repository = InMemoryConnectorSecretBrokerageRepository()
    other = replace(
        record,
        authorization_id="connector-secret-brokerage-authorization.other-tenant",
        organization_id="organization.other",
        environment_id="environment.other",
    )

    assert await repository.add(record) is True
    assert await repository.add(other) is True
    assert (
        await repository.get_by_runtime_trust_in_scope(
            source_runtime_trust_grant_id=record.source_runtime_trust_grant_id,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
        )
        == record
    )
    assert (
        await repository.get_by_runtime_trust_in_scope(
            source_runtime_trust_grant_id=other.source_runtime_trust_grant_id,
            organization_id=other.organization_id,
            environment_id=other.environment_id,
        )
        == other
    )
    assert await repository.list_scope(
        organization_id=record.organization_id,
        environment_id=record.environment_id,
    ) == (record,)


@pytest.mark.asyncio
async def test_secret_brokerage_options_fail_closed_for_expired_runtime_evidence() -> None:
    service, runtime_fixture, runtime_trust, _, _ = await secret_brokerage_fixture()
    runtime_fixture[0]._clock = lambda: runtime_trust.granted_at + timedelta(days=11)

    with pytest.raises(ConnectorSecretBrokerageError, match="source_not_found"):
        await service.list_options(
            actor=secret_brokerage_authorizer(),
            source_runtime_trust_grant_id=runtime_trust.grant_id,
            correlation_id="cor_expired_runtime",
        )


@pytest.mark.asyncio
async def test_secret_brokerage_options_fail_closed_for_expired_configuration_evidence() -> None:
    service, runtime_fixture, runtime_trust, _, _ = await secret_brokerage_fixture()
    runtime_fixture[2]._clock = lambda: runtime_trust.granted_at + timedelta(days=11)

    with pytest.raises(ConnectorSecretBrokerageError, match="source_not_found"):
        await service.list_options(
            actor=secret_brokerage_authorizer(),
            source_runtime_trust_grant_id=runtime_trust.grant_id,
            correlation_id="cor_expired_configuration",
        )


@pytest.mark.asyncio
async def test_secret_brokerage_inventory_and_downstream_fail_closed_when_evidence_expires() -> (
    None
):
    service, _, runtime_trust, profile, policy = await secret_brokerage_fixture()
    record = await authorize_secret_brokerage(service, runtime_trust, profile, policy)
    service._clock = lambda: runtime_trust.granted_at + timedelta(days=11)

    with pytest.raises(ConnectorSecretBrokerageError, match="invalid"):
        await service.list_authorizations(
            actor=secret_brokerage_authorizer(),
            source_runtime_trust_grant_id=runtime_trust.grant_id,
            correlation_id="cor_expired_brokerage_inventory",
        )
    with pytest.raises(ConnectorSecretBrokerageError, match="invalid"):
        await service.runtime_activation_source(authorization_id=record.authorization_id)
    with pytest.raises(ConnectorSecretBrokerageError, match="invalid"):
        await service.get(
            actor=secret_brokerage_authorizer(),
            authorization_id=record.authorization_id,
            correlation_id="cor_expired_brokerage_get",
        )


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
    foreign_runtime_trust = replace(
        runtime_trust,
        grant_id="connector-runtime-trust-grant.foreign",
        organization_id="organization.foreign",
        environment_id="environment.foreign",
    )
    assert asyncio.run(runtime_service.repository.add(foreign_runtime_trust)) is True
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
        endpoint = "/api/v1/connectors/secret-brokerage-authorizations"
        unauthenticated_inventory = client.get(endpoint)
        login_response = login(client)
        inventory_before = client.get(
            endpoint,
            params={"source_runtime_trust_grant_id": runtime_trust.grant_id},
        )
        options_before = client.get(
            f"{endpoint}/options",
            params={"source_runtime_trust_grant_id": runtime_trust.grant_id},
        )
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "broker-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "broker_id": "secret-broker.attacker"},
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
        inventory_after = client.get(
            endpoint,
            params={"source_runtime_trust_grant_id": runtime_trust.grant_id},
        )
        options_after = client.get(
            f"{endpoint}/options",
            params={"source_runtime_trust_grant_id": runtime_trust.grant_id},
        )
        missing_inventory = client.get(
            endpoint,
            params={"source_runtime_trust_grant_id": "connector-runtime-trust-grant.missing"},
        )
        foreign_inventory = client.get(
            endpoint,
            params={"source_runtime_trust_grant_id": foreign_runtime_trust.grant_id},
        )
        foreign_options = client.get(
            f"{endpoint}/options",
            params={"source_runtime_trust_grant_id": foreign_runtime_trust.grant_id},
        )
        missing_options = client.get(
            f"{endpoint}/options",
            params={"source_runtime_trust_grant_id": "connector-runtime-trust-grant.missing"},
        )

    assert unauthenticated_inventory.status_code == 401
    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert inventory_before.status_code == options_before.status_code == 200
    assert inventory_before.json()["data"] == []
    assert len(options_before.json()["data"]) == 1
    option = options_before.json()["data"][0]
    assert option["source_runtime_trust_grant_id"] == runtime_trust.grant_id
    assert option["source_runtime_trust_digest"] == runtime_trust.canonical_digest
    assert option["brokerage_profile_id"] == profile.profile_id
    assert option["brokerage_profile_digest"] == profile.canonical_digest
    assert option["brokerage_policy_id"] == policy.policy_id
    assert option["brokerage_policy_digest"] == policy.canonical_digest
    assert option["required_assurance_level"] == "single_factor"
    assert option["resulting_instance_state"] == "enabled_secret_brokerage_governed"
    assert option["secret_brokerage_governed"] is True
    assert option["secret_lease_issued"] is False
    assert len(inventory_after.json()["data"]) == 1
    inventory = inventory_after.json()["data"][0]
    assert inventory["authorization_id"] == authorization_id
    assert inventory["source_runtime_trust_grant_id"] == runtime_trust.grant_id
    assert inventory["instance_state"] == "enabled_secret_brokerage_governed"
    assert inventory["secret_brokerage_governed"] is True
    assert inventory["credentials_resolved"] is False
    assert options_after.json()["data"] == []
    assert missing_inventory.json()["data"] == []
    assert foreign_inventory.json()["data"] == missing_inventory.json()["data"]
    assert foreign_options.status_code == missing_options.status_code == 404
    assert foreign_options.json()["code"] == missing_options.json()["code"]
    protected_responses = (
        created,
        read,
        inventory_before,
        options_before,
        inventory_after,
        options_after,
        missing_inventory,
        foreign_inventory,
    )
    assert all(item.headers["Cache-Control"] == "no-store" for item in protected_responses)
    data = created.json()["data"]
    assert data["credential_resolution_authorized"] is True
    assert data["secret_lease_issued"] is False and data["credentials_resolved"] is False
    rendered = f"{created.text}\n{read.text}\n{inventory_after.text}\n{options_before.text}".lower()
    for hidden in (
        "credential_profile_id",
        "credential_profile_digest",
        "secret_reference_id",
        "secret_store_profile_id",
        "broker_id",
        "runner_workload_identity_id",
        "lease_handle",
        "request_fingerprint",
        "idempotency_key",
        "password",
        "access_token",
        "bearer_token",
        "command",
    ):
        assert hidden not in rendered
