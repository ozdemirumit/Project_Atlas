from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_capability_enablement import (
    capability_enablement_fixture,
    enable_capabilities,
)
from test_instance_creation import instance_operator
from test_package_acquisition import CollectingAuditSink, FailingAuditSink

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.runtime_trust_memory import (
    InMemoryConnectorRuntimeTrustPolicySource,
    InMemoryConnectorRuntimeTrustProfileSource,
    InMemoryConnectorRuntimeTrustRepository,
)
from atlas.modules.connectors.adapters.runtime_trust_postgres import (
    PostgreSQLConnectorRuntimeTrustRepository,
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
from atlas.modules.connectors.application.runtime_trust import (
    ConnectorRuntimeTrustService,
    _signed_snapshot,
    build_connector_runtime_trust_profile,
    build_development_connector_runtime_trust_policy,
)
from atlas.modules.connectors.application.runtime_trust_ports import ConnectorRuntimeTrustError
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
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject


def runtime_trust_granter(
    subject_id: str = "subject.connector-independent-runtime-trust-granter",
) -> AuthenticatedSubject:
    return replace(instance_operator(subject_id), assurance_level=AssuranceLevel.HARDWARE_BACKED)


async def runtime_trust_fixture(
    *, audit_sink: CollectingAuditSink | FailingAuditSink | None = None
) -> tuple[
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
]:
    (
        enablement_service,
        validation_service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        validation,
        capability_profile,
        enablement_policy,
    ) = await capability_enablement_fixture()
    enablement = await enable_capabilities(
        enablement_service, validation, capability_profile, enablement_policy
    )
    _, registration, _ = await enablement_service.runtime_trust_source(
        enablement_id=enablement.enablement_id
    )
    profile = build_connector_runtime_trust_profile(
        enablement=enablement,
        registration=registration,
        issued_at=enablement.enabled_at,
        expires_at=enablement.enabled_at + timedelta(days=10),
    )
    policy = build_development_connector_runtime_trust_policy(
        organization_id=enablement.organization_id,
        environment_id=enablement.environment_id,
        issued_at=enablement.enabled_at - timedelta(hours=1),
        expires_at=enablement.enabled_at + timedelta(days=10),
    )
    service = ConnectorRuntimeTrustService(
        repository=InMemoryConnectorRuntimeTrustRepository(),
        enablement_source=enablement_service,
        profile_source=InMemoryConnectorRuntimeTrustProfileSource((profile,)),
        policy_source=InMemoryConnectorRuntimeTrustPolicySource((policy,)),
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=enablement.environment_id,
        clock=lambda: enablement.enabled_at,
    )
    return (
        service,
        enablement_service,
        validation_service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        enablement,
        profile,
        policy,
    )


async def grant_runtime_trust(
    service: ConnectorRuntimeTrustService,
    enablement: ConnectorCapabilityEnablementRecord,
    profile: ConnectorRuntimeTrustProfileSnapshot,
    policy: ConnectorRuntimeTrustPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "runtime-trust-001",
) -> ConnectorRuntimeTrustGrantRecord:
    return await service.create(
        actor=actor or runtime_trust_granter(),
        source_enablement_id=enablement.enablement_id,
        source_enablement_digest=enablement.canonical_digest,
        package_digest=enablement.package_digest,
        runtime_profile_id=profile.profile_id,
        runtime_profile_digest=profile.canonical_digest,
        trust_policy_id=policy.policy_id,
        trust_policy_digest=policy.canonical_digest,
        purpose="Bind the exact enabled connector to an isolated runtime without starting it.",
        boundary_only_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_runtime_trust",
    )


@pytest.mark.asyncio
async def test_runtime_trust_grants_only_secret_brokerage_eligibility() -> None:
    audit = CollectingAuditSink()
    service, *_, enablement, profile, policy = await runtime_trust_fixture(audit_sink=audit)
    record = await grant_runtime_trust(service, enablement, profile, policy)
    repeated = await grant_runtime_trust(service, enablement, profile, policy)

    assert record.runtime_boundary_bound and record.runtime_trust_granted
    assert record.eligible_for_secret_brokerage
    assert record.instance_state == "enabled_runtime_trusted"
    assert repeated.reused and repeated.grant_id == record.grant_id
    assert not record.runner_started and not record.package_loaded
    assert not record.credential_resolution_authorized and not record.credentials_resolved
    assert not record.target_connection_authorized and not record.capability_invocation_authorized
    assert not record.execution_authorized and not record.deployment_approved
    assert [item.result_code for item in audit.records] == [
        "connector_runtime_trust_requested",
        "connector_runtime_trust_completed",
    ]


@pytest.mark.asyncio
async def test_runtime_trust_enforces_exact_lineage_boundary_and_separation() -> None:
    service, enablement_service, *_, enablement, profile, policy = await runtime_trust_fixture()
    _, _, actors = await enablement_service.runtime_trust_source(
        enablement_id=enablement.enablement_id
    )
    for subject_id in (*sorted(actors), profile.signed_by, policy.signed_by):
        with pytest.raises(ConnectorRuntimeTrustError, match="separation_required"):
            await grant_runtime_trust(
                service,
                enablement,
                profile,
                policy,
                actor=runtime_trust_granter(subject_id),
                key=f"runtime-trust-{subject_id}",
            )
    with pytest.raises(ConnectorRuntimeTrustError, match="invalid"):
        await service.create(
            actor=runtime_trust_granter(),
            source_enablement_id=enablement.enablement_id,
            source_enablement_digest="f" * 64,
            package_digest=enablement.package_digest,
            runtime_profile_id=profile.profile_id,
            runtime_profile_digest=profile.canonical_digest,
            trust_policy_id=policy.policy_id,
            trust_policy_digest=policy.canonical_digest,
            purpose="Reject mismatched immutable runtime trust lineage evidence.",
            boundary_only_acknowledged=True,
            idempotency_key="runtime-trust-invalid-001",
            correlation_id="cor_invalid",
        )


@pytest.mark.asyncio
async def test_runtime_trust_rejects_unapproved_signed_isolation_profile() -> None:
    (
        _,
        enablement_service,
        *_,
        enablement,
        profile,
        policy,
    ) = await runtime_trust_fixture()
    unsafe = replace(
        profile,
        isolation_profile_id="isolation-profile.unapproved",
        canonical_digest="0" * 64,
    )
    unsafe = replace(unsafe, canonical_digest=_signed_snapshot(unsafe))
    service = ConnectorRuntimeTrustService(
        repository=InMemoryConnectorRuntimeTrustRepository(),
        enablement_source=enablement_service,
        profile_source=InMemoryConnectorRuntimeTrustProfileSource((unsafe,)),
        policy_source=InMemoryConnectorRuntimeTrustPolicySource((policy,)),
        audit_sink=CollectingAuditSink(),
        environment_id=enablement.environment_id,
        clock=lambda: enablement.enabled_at,
    )
    with pytest.raises(ConnectorRuntimeTrustError, match="invalid"):
        await grant_runtime_trust(service, enablement, unsafe, policy)


@pytest.mark.asyncio
async def test_runtime_trust_requires_audit_before_persistence() -> None:
    service, *_, enablement, profile, policy = await runtime_trust_fixture(
        audit_sink=FailingAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await grant_runtime_trust(service, enablement, profile, policy)
    assert (
        await service.repository.get_by_enablement(source_enablement_id=enablement.enablement_id)
        is None
    )


@pytest.mark.asyncio
async def test_runtime_trust_postgres_payload_round_trip_is_bounded() -> None:
    service, *_, enablement, profile, policy = await runtime_trust_fixture()
    record = await grant_runtime_trust(service, enablement, profile, policy)
    raw = ConnectorRuntimeTrustService._normalize(asdict(record))
    assert isinstance(raw, dict)
    restored = PostgreSQLConnectorRuntimeTrustRepository._to_domain(raw)
    assert restored == record
    rendered = repr(raw).lower()
    for hidden in ("endpoint_url", "secret_reference_id", "password", "command", "parameters"):
        assert hidden not in rendered


def test_runtime_trust_api_rejects_caller_controls_and_minimizes_response(
    tmp_path: Path,
) -> None:
    (
        service,
        enablement_service,
        validation_service,
        assignment_service,
        target_service,
        instance_service,
        installation_service,
        registration_service,
        enablement,
        profile,
        policy,
    ) = asyncio.run(runtime_trust_fixture())
    subject = runtime_trust_granter()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.connector-runtime-trust-input.v1",
        "source_enablement_id": enablement.enablement_id,
        "source_enablement_digest": enablement.canonical_digest,
        "package_digest": enablement.package_digest,
        "runtime_profile_id": profile.profile_id,
        "runtime_profile_digest": profile.canonical_digest,
        "trust_policy_id": policy.policy_id,
        "trust_policy_digest": policy.canonical_digest,
        "purpose": "Bind the exact enabled connector to an isolated runtime without starting it.",
    }
    payload[
        "acknowledged_trust_grants_no_runtime_start_secret_target_execution_or_deployment_authority"
    ] = True
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
            runtime_trust_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/runtime-trust-grants"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "trust-api-001"})
        forbidden = client.post(
            endpoint,
            json={**payload, "runner_pool_id": "runner-pool.attacker"},
            headers={
                "Idempotency-Key": "trust-api-002",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "trust-api-001",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        grant_id = created.json()["data"]["grant_id"]
        read = client.get(f"{endpoint}/{grant_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["runtime_trust_granted"] is True and data["runner_started"] is False
    rendered = created.text.lower()
    for hidden in (
        "endpoint_url",
        "target_profile_id",
        "credential_profile_id",
        "secret_reference_id",
        "secret_store_profile_id",
        "request_fingerprint",
        "idempotency_key",
        "password",
        "command",
        "parameters",
    ):
        assert hidden not in rendered
