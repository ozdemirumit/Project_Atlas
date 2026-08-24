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
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


def credential_assigner(
    subject_id: str = "subject.connector-independent-credential-assigner",
) -> AuthenticatedSubject:
    return instance_operator(subject_id)


async def credential_assignment_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
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
    if required_assurance_level is not policy.required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_snapshot(policy))
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
async def test_assignment_default_policy_accepts_development_password_human() -> None:
    service, _, _, _, _, binding, profile, policy = await credential_assignment_fixture()
    actor = replace(
        credential_assigner(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    record = await assign_credential(service, binding, profile, policy, actor=actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.assigned_by == actor.subject_id
    assert not record.runtime_trust_granted and not record.execution_authorized


@pytest.mark.asyncio
async def test_assignment_options_and_inventory_are_verified_scope_bound_and_reloadable() -> None:
    (
        _,
        target_service,
        _,
        _,
        _,
        binding,
        profile,
        policy,
    ) = await credential_assignment_fixture()
    actor = credential_assigner()

    incompatible = replace(
        profile,
        profile_id="connector-credential-profile.incompatible",
        allowed_connector_ids=("connector.other",),
        canonical_digest="0" * 64,
    )
    incompatible = replace(incompatible, canonical_digest=_signed_snapshot(incompatible))
    stale = replace(
        profile,
        profile_id="connector-credential-profile.stale",
        issued_at=binding.bound_at - timedelta(hours=200),
        next_rotation_at=binding.bound_at + timedelta(hours=48),
        expires_at=binding.bound_at + timedelta(hours=96),
        canonical_digest="0" * 64,
    )
    stale = replace(stale, canonical_digest=_signed_snapshot(stale))
    tampered = replace(
        profile,
        profile_id="connector-credential-profile.tampered",
        canonical_digest="f" * 64,
    )
    wrong_scope = replace(
        profile,
        profile_id="connector-credential-profile.wrong-scope",
        organization_id="organization.other",
        canonical_digest="0" * 64,
    )
    wrong_scope = replace(wrong_scope, canonical_digest=_signed_snapshot(wrong_scope))
    separated = replace(
        profile,
        profile_id="connector-credential-profile.separated",
        signed_by=actor.subject_id,
        canonical_digest="0" * 64,
    )
    separated = replace(separated, canonical_digest=_signed_snapshot(separated))
    separation_policy = replace(
        policy,
        policy_id="connector-credential-assignment-policy.separated",
        required_credential_profile_signer_id=actor.subject_id,
        canonical_digest="0" * 64,
    )
    separation_policy = replace(
        separation_policy,
        canonical_digest=_signed_snapshot(separation_policy),
    )
    wrong_scope_policy = replace(
        policy,
        policy_id="connector-credential-assignment-policy.wrong-scope",
        environment_id="environment.other",
        canonical_digest="0" * 64,
    )
    wrong_scope_policy = replace(
        wrong_scope_policy,
        canonical_digest=_signed_snapshot(wrong_scope_policy),
    )
    service = ConnectorCredentialAssignmentService(
        repository=InMemoryConnectorCredentialAssignmentRepository(),
        target_source=target_service,
        credential_profile_source=InMemoryConnectorCredentialProfileSource(
            (profile, incompatible, stale, tampered, wrong_scope, separated)
        ),
        policy_source=InMemoryConnectorCredentialAssignmentPolicySource(
            (policy, separation_policy, wrong_scope_policy)
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=binding.environment_id,
        clock=lambda: binding.bound_at,
    )

    options = await service.list_options(
        actor=actor,
        source_target_binding_id=binding.binding_id,
        correlation_id="cor_credential_options",
    )

    assert len(options) == 1
    option = options[0]
    assert option.credential_profile_id == profile.profile_id
    assert option.credential_profile_digest == profile.canonical_digest
    assert option.credential_policy_id == policy.policy_id
    assert option.credential_policy_digest == policy.canonical_digest
    assert option.resulting_instance_state == "disabled_credentials_assigned"

    with pytest.raises(ConnectorCredentialAssignmentError, match="record_not_found"):
        await service.list_options(
            actor=replace(actor, organization_id="organization.other"),
            source_target_binding_id=binding.binding_id,
            correlation_id="cor_credential_options_wrong_scope",
        )

    assignment = await assign_credential(service, binding, profile, policy, actor=actor)
    inventory = await service.list_assignments(
        actor=actor,
        source_target_binding_id=binding.binding_id,
        correlation_id="cor_credential_inventory",
    )
    all_assignments = await service.list_assignments(
        actor=actor,
        source_target_binding_id=None,
        correlation_id="cor_credential_inventory_all",
    )
    exhausted = await service.list_options(
        actor=actor,
        source_target_binding_id=binding.binding_id,
        correlation_id="cor_credential_options_after_assignment",
    )
    foreign_repository = InMemoryConnectorCredentialAssignmentRepository()
    await foreign_repository.add(replace(assignment, organization_id="organization.other"))
    foreign_service = ConnectorCredentialAssignmentService(
        repository=foreign_repository,
        target_source=target_service,
        credential_profile_source=InMemoryConnectorCredentialProfileSource((profile,)),
        policy_source=InMemoryConnectorCredentialAssignmentPolicySource((policy,)),
        audit_sink=CollectingAuditSink(),
        environment_id=binding.environment_id,
        clock=lambda: binding.bound_at,
    )
    foreign_inventory = await foreign_service.list_assignments(
        actor=actor,
        source_target_binding_id=binding.binding_id,
        correlation_id="cor_credential_inventory_foreign_scope",
    )

    assert inventory == all_assignments == (assignment,)
    assert exhausted == ()
    assert foreign_inventory == ()


@pytest.mark.asyncio
async def test_downstream_assignment_source_revalidates_current_profile_and_policy() -> None:
    service, _, _, _, _, binding, profile, policy = await credential_assignment_fixture()
    record = await assign_credential(service, binding, profile, policy)
    service._clock = lambda: profile.expires_at + timedelta(seconds=1)

    with pytest.raises(ConnectorCredentialAssignmentError, match="assignment_invalid"):
        await service.configuration_validation_source(assignment_id=record.assignment_id)
    with pytest.raises(ConnectorCredentialAssignmentError, match="assignment_invalid"):
        await service.secret_brokerage_source(
            credential_profile_id=record.credential_profile_id,
            instance_id=record.instance_id,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "required_assurance_level",
    (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED),
)
async def test_assignment_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, _, _, _, binding, profile, policy = await credential_assignment_fixture(
        required_assurance_level=required_assurance_level
    )
    actor = replace(
        credential_assigner(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(ConnectorCredentialAssignmentError, match="assignment_invalid"):
        await assign_credential(service, binding, profile, policy, actor=actor)


@pytest.mark.asyncio
async def test_assignment_rejects_non_human_identity() -> None:
    service, _, _, _, _, binding, profile, policy = await credential_assignment_fixture()
    actor = replace(credential_assigner(), kind=SubjectKind.SERVICE)

    with pytest.raises(
        ConnectorCredentialAssignmentError, match="credential_assignment_human_required"
    ):
        await assign_credential(service, binding, profile, policy, actor=actor)


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
        endpoint = "/api/v1/connectors/credential-assignments"
        unauthenticated_options = client.get(
            f"{endpoint}/options",
            params={"source_target_binding_id": binding.binding_id},
        )
        login_response = login(client)
        options = client.get(
            f"{endpoint}/options",
            params={"source_target_binding_id": binding.binding_id},
        )
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
        inventory = client.get(
            endpoint,
            params={"source_target_binding_id": binding.binding_id},
        )
        unmatched = client.get(
            endpoint,
            params={"source_target_binding_id": "connector-target-configuration.missing"},
        )
        exhausted = client.get(
            f"{endpoint}/options",
            params={"source_target_binding_id": binding.binding_id},
        )

    assert unauthenticated_options.status_code == 401
    assert denied.status_code == 403 and forbidden.status_code == 422
    assert (
        options.status_code
        == read.status_code
        == inventory.status_code
        == unmatched.status_code
        == exhausted.status_code
        == 200
    )
    assert len(options.json()["data"]) == len(inventory.json()["data"]) == 1
    assert options.json()["data"][0]["credential_profile_id"] == profile.profile_id
    assert inventory.json()["data"][0]["assignment_id"] == assignment_id
    assert unmatched.json()["data"] == exhausted.json()["data"] == []
    assert (
        created.headers["Cache-Control"]
        == read.headers["Cache-Control"]
        == inventory.headers["Cache-Control"]
        == unmatched.headers["Cache-Control"]
        == options.headers["Cache-Control"]
        == exhausted.headers["Cache-Control"]
        == "no-store"
    )
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

    minimized_responses = (options, inventory, unmatched, exhausted)
    minimized = "".join(item.text for item in minimized_responses).lower()
    exposed_keys = {
        key for item in minimized_responses for record in item.json()["data"] for key in record
    }
    for hidden_key in (
        "secret_reference",
        "secret_reference_id",
        "secret_store",
        "secret_store_profile_id",
        "vault",
        "user",
        "username",
        "password",
        "token",
        "token_value",
        "access_token",
        "key",
        "private_key",
        "cert",
        "certificate",
        "endpoint",
        "host",
        "ip_address",
        "port",
        "target_id",
        "target_profile_id",
        "target_profile_digest",
        "site_id",
        "target_type",
        "target_product",
        "signed_by",
        "signature",
        "request_fingerprint",
        "idempotency_key",
        "endpoint_origin",
    ):
        assert hidden_key not in exposed_keys
    for hidden_value in (
        "secret-reference.connector.storage-reader",
        "secret-store-profile.enterprise",
    ):
        assert hidden_value not in minimized
