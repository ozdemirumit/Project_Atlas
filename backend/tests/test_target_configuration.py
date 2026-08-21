from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_instance_creation import (
    FailSecondAuditSink,
    create_instance,
    instance_fixture,
    instance_operator,
)
from test_package_acquisition import CollectingAuditSink, FailingAuditSink

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.target_configuration_memory import (
    InMemoryConnectorTargetConfigurationPolicySource,
    InMemoryConnectorTargetConfigurationRepository,
    InMemoryConnectorTargetProfileSource,
)
from atlas.modules.connectors.adapters.target_configuration_postgres import (
    PostgreSQLConnectorTargetConfigurationRepository,
)
from atlas.modules.connectors.application.instance_creation import (
    ConnectorInstanceCreationService,
)
from atlas.modules.connectors.application.package_installation import PackageInstallationService
from atlas.modules.connectors.application.package_registration import PackageRegistrationService
from atlas.modules.connectors.application.target_configuration import (
    ConnectorTargetConfigurationService,
    _signed_snapshot,
    build_development_connector_target_configuration_policy,
    build_development_connector_target_profile,
)
from atlas.modules.connectors.application.target_configuration_ports import (
    ConnectorTargetConfigurationError,
)
from atlas.modules.connectors.domain.instance_creation import ConnectorInstanceRecord
from atlas.modules.connectors.domain.target_configuration import (
    ConnectorTargetConfigurationBinding,
    ConnectorTargetConfigurationPolicySnapshot,
    ConnectorTargetProfileSnapshot,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


def target_binder(
    subject_id: str = "subject.connector-independent-target-binder",
) -> AuthenticatedSubject:
    return instance_operator(subject_id)


async def target_configuration_fixture(
    *,
    audit_sink: CollectingAuditSink | FailingAuditSink | FailSecondAuditSink | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    ConnectorTargetConfigurationService,
    ConnectorInstanceCreationService,
    PackageInstallationService,
    PackageRegistrationService,
    ConnectorInstanceRecord,
    ConnectorTargetProfileSnapshot,
    ConnectorTargetConfigurationPolicySnapshot,
]:
    (
        instance_service,
        installation_service,
        registration_service,
        _publication_service,
        installation,
        instance_policy,
    ) = await instance_fixture()
    instance = await create_instance(instance_service, installation, instance_policy)
    profile = build_development_connector_target_profile(
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        issued_at=instance.created_at - timedelta(hours=1),
        expires_at=instance.created_at + timedelta(days=2),
    )
    policy = build_development_connector_target_configuration_policy(
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        issued_at=instance.created_at - timedelta(hours=1),
        expires_at=instance.created_at + timedelta(days=2),
    )
    if required_assurance_level is not policy.required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_snapshot(policy))
    service = ConnectorTargetConfigurationService(
        repository=InMemoryConnectorTargetConfigurationRepository(),
        instance_source=instance_service,
        target_profile_source=InMemoryConnectorTargetProfileSource((profile,)),
        policy_source=InMemoryConnectorTargetConfigurationPolicySource((policy,)),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=instance.environment_id,
        clock=lambda: instance.created_at,
    )
    return (
        service,
        instance_service,
        installation_service,
        registration_service,
        instance,
        profile,
        policy,
    )


async def bind_target(
    service: ConnectorTargetConfigurationService,
    instance: ConnectorInstanceRecord,
    profile: ConnectorTargetProfileSnapshot,
    policy: ConnectorTargetConfigurationPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "target-configuration-001",
) -> ConnectorTargetConfigurationBinding:
    return await service.create(
        actor=actor or target_binder(),
        source_instance_record_id=instance.record_id,
        source_instance_record_digest=instance.canonical_digest,
        package_digest=instance.package_digest,
        target_profile_id=profile.profile_id,
        target_profile_digest=profile.canonical_digest,
        configuration_policy_id=policy.policy_id,
        configuration_policy_digest=policy.canonical_digest,
        purpose="Bind signed target configuration without credentials or runtime authority.",
        acknowledged_binding_grants_no_credentials_enablement_or_runtime_authority=True,
        idempotency_key=key,
        correlation_id="cor_target_configuration",
    )


@pytest.mark.asyncio
async def test_target_binding_grants_only_credential_governance_eligibility() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, instance, profile, policy = await target_configuration_fixture(
        audit_sink=audit
    )
    binding = await bind_target(service, instance, profile, policy)
    repeated = await bind_target(service, instance, profile, policy)

    assert binding.target_configured and binding.eligible_for_credential_governance
    assert binding.instance_state == "disabled_target_configured"
    assert repeated.reused and repeated.binding_id == binding.binding_id
    assert not binding.credentials_resolved and not binding.connector_enabled
    assert not binding.runtime_trust_granted and not binding.execution_authorized
    assert not binding.deployment_approved and not binding.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == [
        "connector_target_configuration_requested",
        "connector_target_configuration_completed",
    ]


@pytest.mark.asyncio
async def test_target_binding_default_policy_accepts_development_password_human() -> None:
    service, _, _, _, instance, profile, policy = await target_configuration_fixture()
    actor = replace(
        target_binder(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    binding = await bind_target(service, instance, profile, policy, actor=actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert binding.bound_by == actor.subject_id
    assert not binding.runtime_trust_granted and not binding.execution_authorized


@pytest.mark.asyncio
async def test_target_options_and_inventory_are_scope_bound_and_reloadable() -> None:
    service, _, _, _, instance, profile, policy = await target_configuration_fixture()
    actor = target_binder()

    options = await service.list_options(
        actor=actor,
        source_instance_record_id=instance.record_id,
        correlation_id="cor_target_options",
    )

    assert len(options) == 1
    option = options[0]
    assert option.target_profile_id == profile.profile_id
    assert option.target_profile_digest == profile.canonical_digest
    assert option.configuration_policy_id == policy.policy_id
    assert option.configuration_policy_digest == policy.canonical_digest
    assert option.resulting_instance_state == "disabled_target_configured"

    binding = await bind_target(service, instance, profile, policy, actor=actor)
    inventory = await service.list_bindings(
        actor=actor,
        source_instance_record_id=instance.record_id,
        correlation_id="cor_target_inventory",
    )
    exhausted = await service.list_options(
        actor=actor,
        source_instance_record_id=instance.record_id,
        correlation_id="cor_target_options_after_binding",
    )

    assert inventory == (binding,)
    assert exhausted == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "required_assurance_level",
    (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED),
)
async def test_target_binding_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, _, _, instance, profile, policy = await target_configuration_fixture(
        required_assurance_level=required_assurance_level
    )
    actor = replace(
        target_binder(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(ConnectorTargetConfigurationError, match="binding_invalid"):
        await bind_target(service, instance, profile, policy, actor=actor)


@pytest.mark.asyncio
async def test_target_binding_rejects_non_human_identity() -> None:
    service, _, _, _, instance, profile, policy = await target_configuration_fixture()
    actor = replace(target_binder(), kind=SubjectKind.SERVICE)

    with pytest.raises(
        ConnectorTargetConfigurationError, match="target_configuration_human_required"
    ):
        await bind_target(service, instance, profile, policy, actor=actor)


@pytest.mark.asyncio
async def test_target_binding_enforces_exact_source_profile_policy_and_separation() -> None:
    service, instance_source, _, _, instance, profile, policy = await target_configuration_fixture()
    _, _, _, _, actors = await instance_source.target_configuration_source(
        record_id=instance.record_id
    )
    for subject_id in (*sorted(actors), profile.signed_by, policy.signed_by):
        with pytest.raises(ConnectorTargetConfigurationError, match="separation_required"):
            await bind_target(
                service,
                instance,
                profile,
                policy,
                actor=target_binder(subject_id),
                key=f"target-{subject_id}",
            )
    with pytest.raises(ConnectorTargetConfigurationError, match="binding_invalid"):
        await service.create(
            actor=target_binder(),
            source_instance_record_id=instance.record_id,
            source_instance_record_digest="f" * 64,
            package_digest=instance.package_digest,
            target_profile_id=profile.profile_id,
            target_profile_digest=profile.canonical_digest,
            configuration_policy_id=policy.policy_id,
            configuration_policy_digest=policy.canonical_digest,
            purpose="Bind signed target configuration without credentials or runtime authority.",
            acknowledged_binding_grants_no_credentials_enablement_or_runtime_authority=True,
            idempotency_key="target-binding-invalid",
            correlation_id="cor_target_configuration",
        )


def test_target_profile_rejects_raw_unsafe_network_origins() -> None:
    _, _, _, _, instance, profile, _ = asyncio.run(target_configuration_fixture())
    del instance
    for origin in (
        "http://storage-api.atlas.internal:443",
        "https://127.0.0.1:443",
        "https://user:pass@storage-api.atlas.internal:443",
        "https://storage-api.atlas.internal:443/admin?token=x",
    ):
        with pytest.raises(ValueError, match="profile contract"):
            replace(profile, endpoint_origin=origin)


@pytest.mark.asyncio
async def test_target_binding_required_audits_precede_persistence() -> None:
    first, _, _, _, instance, profile, policy = await target_configuration_fixture(
        audit_sink=FailingAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await bind_target(first, instance, profile, policy)
    assert first.repository._bindings == {}  # type: ignore[attr-defined]

    second, _, _, _, instance, profile, policy = await target_configuration_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(RuntimeError, match="completion audit unavailable"):
        await bind_target(second, instance, profile, policy)
    assert second.repository._bindings == {}  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_target_binding_postgres_round_trip_preserves_internal_target_identity() -> None:
    service, _, _, _, instance, profile, policy = await target_configuration_fixture()
    binding = await bind_target(service, instance, profile, policy)
    raw = ConnectorTargetConfigurationService._normalize(asdict(binding))
    assert isinstance(raw, dict)
    restored = PostgreSQLConnectorTargetConfigurationRepository._to_domain(raw)
    assert restored == binding
    assert restored.target_id == profile.target_id


def test_target_binding_api_rejects_raw_endpoint_and_minimizes_response(tmp_path: Path) -> None:
    (
        service,
        instance_service,
        installation_service,
        registration_service,
        instance,
        profile,
        policy,
    ) = asyncio.run(target_configuration_fixture())
    subject = target_binder()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload = {
        "schema_version": "atlas.connector-target-configuration-input.v1",
        "source_instance_record_id": instance.record_id,
        "source_instance_record_digest": instance.canonical_digest,
        "package_digest": instance.package_digest,
        "target_profile_id": profile.profile_id,
        "target_profile_digest": profile.canonical_digest,
        "configuration_policy_id": policy.policy_id,
        "configuration_policy_digest": policy.canonical_digest,
        "purpose": "Bind signed target configuration without credentials or runtime authority.",
        "acknowledged_binding_grants_no_credentials_enablement_or_runtime_authority": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_registration_service=registration_service,
            package_installation_service=installation_service,
            connector_instance_creation_service=instance_service,
            target_configuration_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/target-configuration-bindings"
        options = client.get(
            f"{endpoint}/options",
            params={"source_instance_record_id": instance.record_id},
        )
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "target-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "endpoint_origin": "https://caller.example:443"},
            headers={
                "Idempotency-Key": "target-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "target-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        binding_id = created.json()["data"]["binding_id"]
        read = client.get(f"{endpoint}/{binding_id}")
        inventory = client.get(
            endpoint,
            params={"source_instance_record_id": instance.record_id},
        )

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert options.status_code == read.status_code == inventory.status_code == 200
    assert len(options.json()["data"]) == len(inventory.json()["data"]) == 1
    assert options.json()["data"][0]["target_profile_id"] == profile.profile_id
    assert inventory.json()["data"][0]["binding_id"] == binding_id
    assert (
        created.headers["Cache-Control"]
        == read.headers["Cache-Control"]
        == inventory.headers["Cache-Control"]
        == options.headers["Cache-Control"]
        == "no-store"
    )
    data = created.json()["data"]
    assert data["target_configured"] is True and data["connector_enabled"] is False
    assert data["instance_state"] == "disabled_target_configured"
    rendered = (created.text + options.text + inventory.text).lower()
    for hidden in (
        "endpoint_origin",
        "storage-api.atlas.internal",
        "target_id",
        "trust_profile",
        "network_route",
        "proxy_profile",
        "request_fingerprint",
        "idempotency_key",
        "secret_reference",
    ):
        assert hidden not in rendered
