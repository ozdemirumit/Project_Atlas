from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_connector_upgrade_readiness import UpgradePackageSource, upgrade_package
from test_instance_creation import create_instance, instance_fixture, instance_operator
from test_package_acquisition import CollectingAuditSink, FailingAuditSink
from test_target_configuration import bind_target, target_configuration_fixture

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.target_configuration_memory import (
    InMemoryConnectorTargetConfigurationRepository,
)
from atlas.modules.connectors.adapters.upgrade_approval_memory import (
    InMemoryConnectorUpgradeApprovalPolicySource,
    InMemoryConnectorUpgradeApprovalRepository,
    InMemoryConnectorUpgradeAuditReadinessSource,
    InMemoryConnectorUpgradeItsmChangeEvidenceSource,
    InMemoryConnectorUpgradeMaintenanceWindowEvidenceSource,
    InMemoryConnectorUpgradeSigningProviderOnboardingPolicySource,
)
from atlas.modules.connectors.adapters.upgrade_approval_postgres import (
    PostgreSQLConnectorUpgradeApprovalRepository,
)
from atlas.modules.connectors.adapters.upgrade_evidence_authenticity_memory import (
    NonProductionHmacUpgradeEvidenceAuthenticityProvider,
    UnavailableUpgradeEvidenceAuthenticityProvider,
)
from atlas.modules.connectors.adapters.upgrade_onboarding_policy_authenticity_memory import (
    HmacConnectorUpgradeSigningProviderOnboardingPolicyVerifier,
    InMemoryConnectorUpgradeSigningProviderOnboardingPolicyAttestationSource,
    InMemoryConnectorUpgradeSigningProviderOnboardingPolicyTrustSource,
)
from atlas.modules.connectors.application.instance_creation import (
    ConnectorInstanceCreationService,
)
from atlas.modules.connectors.application.package_installation import PackageInstallationService
from atlas.modules.connectors.application.package_registration import PackageRegistrationService
from atlas.modules.connectors.application.registry_publication import RegistryPublicationService
from atlas.modules.connectors.application.upgrade_approval import (
    ConnectorUpgradeApprovalService,
    build_development_connector_upgrade_approval_policy,
    build_development_connector_upgrade_signing_provider_onboarding_policy,
    build_development_connector_upgrade_signing_provider_onboarding_policy_attestation,
    build_development_connector_upgrade_signing_provider_onboarding_policy_trust_key,
)
from atlas.modules.connectors.application.upgrade_approval_ports import (
    ConnectorUpgradeApprovalError,
)
from atlas.modules.connectors.application.upgrade_evidence_authenticity_ports import (
    ConnectorUpgradeEvidenceAuthenticityError,
)
from atlas.modules.connectors.application.upgrade_readiness import (
    ConnectorUpgradeReadinessService,
)
from atlas.modules.connectors.domain.instance_creation import ConnectorInstanceRecord
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationReceipt,
)
from atlas.modules.connectors.domain.upgrade_approval import (
    ConnectorUpgradeApprovalOutcome,
    ConnectorUpgradeApprovalState,
    ConnectorUpgradeAuditReadinessEvidence,
    ConnectorUpgradeEvidenceReceiptVerificationState,
    ConnectorUpgradeItsmChangeEvidence,
    ConnectorUpgradeMaintenanceWindowEvidence,
)
from atlas.modules.connectors.domain.upgrade_evidence_authenticity import (
    ConnectorUpgradeEvidenceAuthenticityState,
    ConnectorUpgradeEvidenceSignature,
    ConnectorUpgradeEvidenceSigningKey,
    ConnectorUpgradeEvidenceSigningKeyEffectiveState,
    ConnectorUpgradeEvidenceSigningKeyState,
    ConnectorUpgradeEvidenceSigningKeyTrust,
    ConnectorUpgradeEvidenceSigningProviderDiagnostic,
    ConnectorUpgradeEvidenceSigningProviderTrust,
    ConnectorUpgradeSigningProviderConformanceState,
    ConnectorUpgradeSigningProviderOnboardingEvidence,
    ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceCheckState,
    ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceState,
    ConnectorUpgradeSigningProviderOnboardingPolicySnapshot,
    ConnectorUpgradeSigningProviderOnboardingPolicyTrustKey,
    ConnectorUpgradeSigningProviderOnboardingPolicyTrustKeyState,
    ConnectorUpgradeSigningProviderOnboardingRequirementState,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticationMethod


async def approval_fixture(
    *,
    clock: Callable[[], datetime] | None = None,
    audit_readiness_source: InMemoryConnectorUpgradeAuditReadinessSource | None = None,
    itsm_change_evidence_source: InMemoryConnectorUpgradeItsmChangeEvidenceSource | None = None,
    maintenance_window_evidence_source: (
        InMemoryConnectorUpgradeMaintenanceWindowEvidenceSource | None
    ) = None,
) -> tuple[
    ConnectorUpgradeApprovalService,
    ConnectorUpgradeReadinessService,
    ConnectorInstanceCreationService,
    PackageInstallationService,
    PackageRegistrationService,
    RegistryPublicationService,
    tuple[ConnectorInstanceRecord, ConnectorPackageInstallationReceipt],
    CollectingAuditSink,
]:
    audit = CollectingAuditSink()
    (
        instance_service,
        package_service,
        registration_service,
        publication_service,
        installation,
        policy,
    ) = await instance_fixture()
    instance = await create_instance(instance_service, installation, policy)
    (
        current_receipt,
        _,
        current_registration,
        _,
    ) = await package_service.connector_instance_creation_source(receipt_id=installation.receipt_id)
    candidate_receipt, candidate_registration = upgrade_package(
        current_receipt, current_registration
    )
    now = installation.installed_at + timedelta(hours=2)
    resolved_clock = clock or (lambda: now)
    upgrade_service = ConnectorUpgradeReadinessService(
        instance_repository=instance_service.repository,
        target_repository=InMemoryConnectorTargetConfigurationRepository(),
        package_source=UpgradePackageSource(
            ((current_receipt, current_registration), (candidate_receipt, candidate_registration))
        ),
        audit_sink=audit,
        environment_id=instance.environment_id,
        clock=resolved_clock,
    )
    approval_policy = build_development_connector_upgrade_approval_policy(
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=1),
    )
    onboarding_policy = build_development_connector_upgrade_signing_provider_onboarding_policy(
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=1),
    )
    onboarding_policy_key_material = b"connector-onboarding-policy-authenticity-test-key"
    onboarding_policy_trust_key = (
        build_development_connector_upgrade_signing_provider_onboarding_policy_trust_key(
            organization_id=instance.organization_id,
            environment_id=instance.environment_id,
            not_before=now - timedelta(hours=1),
            expires_at=now + timedelta(days=1),
        )
    )
    onboarding_policy_attestation = (
        build_development_connector_upgrade_signing_provider_onboarding_policy_attestation(
            policy=onboarding_policy,
            trust_key=onboarding_policy_trust_key,
            key_material=onboarding_policy_key_material,
            issued_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=1),
        )
    )
    service = ConnectorUpgradeApprovalService(
        repository=InMemoryConnectorUpgradeApprovalRepository(),
        policy_source=InMemoryConnectorUpgradeApprovalPolicySource((approval_policy,)),
        upgrade_service=upgrade_service,
        audit_sink=audit,
        environment_id=instance.environment_id,
        audit_readiness_source=audit_readiness_source,
        itsm_change_evidence_source=itsm_change_evidence_source,
        maintenance_window_evidence_source=maintenance_window_evidence_source,
        evidence_authenticity_provider=NonProductionHmacUpgradeEvidenceAuthenticityProvider(
            key=ConnectorUpgradeEvidenceSigningKey(
                key_id="key.connector-upgrade-evidence.test",
                key_version="version.1",
                signer_profile_id="signer-profile.nonproduction-hmac",
                signer_workload_id="workload.connector-upgrade-evidence-signer",
                algorithm="algorithm.hmac-sha256-nonproduction",
                organization_id=instance.organization_id,
                environment_id=instance.environment_id,
                state=ConnectorUpgradeEvidenceSigningKeyState.ACTIVE,
                not_before=now - timedelta(days=1),
                expires_at=now + timedelta(days=2),
            ),
            key_material=b"connector-upgrade-evidence-test-key-material-v1",
            clock=resolved_clock,
        ),
        signing_provider_onboarding_policy_source=(
            InMemoryConnectorUpgradeSigningProviderOnboardingPolicySource((onboarding_policy,))
        ),
        signing_provider_onboarding_policy_attestation_source=(
            InMemoryConnectorUpgradeSigningProviderOnboardingPolicyAttestationSource(
                (onboarding_policy_attestation,)
            )
        ),
        signing_provider_onboarding_policy_trust_source=(
            InMemoryConnectorUpgradeSigningProviderOnboardingPolicyTrustSource(
                (onboarding_policy_trust_key,)
            )
        ),
        signing_provider_onboarding_policy_verifier=(
            HmacConnectorUpgradeSigningProviderOnboardingPolicyVerifier(
                key_id=onboarding_policy_trust_key.key_id,
                key_version=onboarding_policy_trust_key.key_version,
                key_material=onboarding_policy_key_material,
            )
        ),
        clock=resolved_clock,
    )
    return (
        service,
        upgrade_service,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        (instance, candidate_receipt),
        audit,
    )


@pytest.mark.asyncio
async def test_signing_key_trust_inventory_is_scoped_audited_and_non_authoritative() -> None:
    service, _, _, _, _, _, sources, audit = await approval_fixture()
    instance, _ = sources
    actor = replace(
        instance_operator("subject.connector-upgrade-trust-auditor"),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    inventory = await service.signing_key_trust_inventory(
        actor=actor,
        correlation_id="correlation.connector-upgrade-signing-key-trust",
    )

    assert inventory.organization_id == instance.organization_id
    assert inventory.environment_id == instance.environment_id
    assert inventory.provider_class == "provider.nonproduction-hmac"
    assert inventory.provider_available and not inventory.production_approved
    assert len(inventory.keys) == 1
    key = inventory.keys[0]
    assert key.effective_state is ConnectorUpgradeEvidenceSigningKeyEffectiveState.ACTIVE
    assert key.signing_eligible and key.verification_trusted
    assert not inventory.key_management_authorized and not inventory.signing_authorized
    assert not inventory.execution_authorized and not inventory.infrastructure_mutation_performed
    assert audit.records[-1].result_code == "connector_upgrade_signing_provider_available"
    assert audit.records[-1].target_metadata == (
        ("provider_class", "provider.nonproduction-hmac"),
        ("key_count", "1"),
        ("key_management_authorized", "false"),
        ("execution_authorized", "false"),
    )


@pytest.mark.asyncio
async def test_signing_key_trust_inventory_fails_closed_for_scope_provider_and_audit() -> None:
    service, _, _, _, _, _, sources, _ = await approval_fixture()
    instance, _ = sources
    actor = instance_operator("subject.connector-upgrade-trust-fail-closed")
    provider = service._evidence_authenticity_provider
    assert provider is not None
    with pytest.raises(
        ConnectorUpgradeEvidenceAuthenticityError,
        match="connector_upgrade_evidence_signing_key_scope_invalid",
    ):
        await provider.trust_inventory(
            organization_id="organization.foreign",
            environment_id=instance.environment_id,
        )

    service._evidence_authenticity_provider = UnavailableUpgradeEvidenceAuthenticityProvider()
    unavailable = await service.signing_key_trust_inventory(
        actor=actor,
        correlation_id="correlation.connector-upgrade-signing-key-trust-unavailable",
    )
    assert unavailable.provider_state == "unavailable"
    assert not unavailable.provider_available and not unavailable.production_approved
    assert unavailable.keys == ()

    service._audit_sink = FailingAuditSink()
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.signing_key_trust_inventory(
            actor=actor,
            correlation_id="correlation.connector-upgrade-signing-key-trust-audit-failed",
        )


@pytest.mark.asyncio
async def test_signing_provider_conformance_is_bounded_idempotent_and_non_authoritative() -> None:
    service, _, _, _, _, _, sources, audit = await approval_fixture()
    instance, _ = sources
    actor = replace(
        instance_operator("subject.connector-upgrade-conformance-auditor"),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )
    assessment = await service.assess_signing_provider_conformance(
        actor=actor,
        acknowledged_diagnostic_grants_no_key_receipt_or_execution_authority=True,
        idempotency_key="connector-upgrade-provider-conformance-test",
        correlation_id="correlation.connector-upgrade-provider-conformance",
    )
    replay = await service.assess_signing_provider_conformance(
        actor=actor,
        acknowledged_diagnostic_grants_no_key_receipt_or_execution_authority=True,
        idempotency_key="connector-upgrade-provider-conformance-test",
        correlation_id="correlation.connector-upgrade-provider-conformance",
    )
    latest = await service.latest_signing_provider_conformance(
        actor=actor,
        correlation_id="correlation.connector-upgrade-provider-conformance-read",
    )

    assert assessment.state is ConnectorUpgradeSigningProviderConformanceState.CONFORMANT
    assert assessment.organization_id == instance.organization_id
    assert assessment.environment_id == instance.environment_id
    assert assessment.provider_class == "provider.nonproduction-hmac"
    assert not assessment.production_approved
    assert assessment.key_id == "key.connector-upgrade-evidence.test"
    assert assessment.algorithm == "algorithm.hmac-sha256-nonproduction"
    assert assessment.signing_provider_conformant and assessment.diagnostic_only
    assert not assessment.key_management_authorized
    assert not assessment.receipt_signing_authorized
    assert not assessment.execution_authorized
    assert not assessment.infrastructure_mutation_performed
    assert replay.reused and replay.canonical_digest == assessment.canonical_digest
    assert latest == assessment
    assert "signature" not in asdict(assessment)
    assert "key_material" not in asdict(assessment)
    assert [record.result_code for record in audit.records][-3:] == [
        "connector_upgrade_signing_provider_conformance_conformant",
        "connector_upgrade_signing_provider_conformance_reused",
        "connector_upgrade_signing_provider_conformance_read",
    ]
    restored = PostgreSQLConnectorUpgradeApprovalRepository._signing_provider_conformance_to_domain(
        cast(
            dict[str, object],
            ConnectorUpgradeApprovalService._normalize(asdict(assessment)),
        )
    )
    assert restored == assessment
    service._audit_sink = FailingAuditSink()
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.latest_signing_provider_conformance(
            actor=actor,
            correlation_id="correlation.connector-upgrade-provider-conformance-audit-failed",
        )


class _FailingConformanceProvider:
    def __init__(self, delegate: object, phase: str) -> None:
        self._delegate = cast(NonProductionHmacUpgradeEvidenceAuthenticityProvider, delegate)
        self._phase = phase

    async def trust_inventory(
        self, *, organization_id: str, environment_id: str
    ) -> ConnectorUpgradeEvidenceSigningProviderTrust:
        return await self._delegate.trust_inventory(
            organization_id=organization_id, environment_id=environment_id
        )

    async def active_key(
        self, *, organization_id: str, environment_id: str
    ) -> ConnectorUpgradeEvidenceSigningKey:
        if self._phase == "ineligible":
            raise ConnectorUpgradeEvidenceAuthenticityError(
                "connector_upgrade_evidence_signing_key_disabled"
            )
        return await self._delegate.active_key(
            organization_id=organization_id, environment_id=environment_id
        )

    async def sign(
        self,
        *,
        key: ConnectorUpgradeEvidenceSigningKey,
        payload_digest: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> ConnectorUpgradeEvidenceSignature:
        if self._phase == "sign":
            raise ConnectorUpgradeEvidenceAuthenticityError("diagnostic_sign_failed")
        return await self._delegate.sign(
            key=key,
            payload_digest=payload_digest,
            issued_at=issued_at,
            expires_at=expires_at,
        )

    async def diagnostic_sign_and_verify(
        self,
        *,
        organization_id: str,
        environment_id: str,
        challenge_digest: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> ConnectorUpgradeEvidenceSigningProviderDiagnostic:
        del challenge_digest, issued_at, expires_at
        key = await self._delegate.active_key(
            organization_id=organization_id, environment_id=environment_id
        )
        state = {
            "sign": ConnectorUpgradeSigningProviderConformanceState.SIGN_FAILED,
            "verify": ConnectorUpgradeSigningProviderConformanceState.VERIFY_FAILED,
        }[self._phase]
        return ConnectorUpgradeEvidenceSigningProviderDiagnostic(
            provider_class="provider.nonproduction-hmac",
            organization_id=organization_id,
            environment_id=environment_id,
            key=key,
            state=state,
        )

    async def verify(
        self,
        *,
        signature: ConnectorUpgradeEvidenceSignature,
        payload_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorUpgradeEvidenceSigningKey:
        if self._phase == "verify":
            raise ConnectorUpgradeEvidenceAuthenticityError("diagnostic_verify_failed")
        return await self._delegate.verify(
            signature=signature,
            payload_digest=payload_digest,
            organization_id=organization_id,
            environment_id=environment_id,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_mode", "expected"),
    (
        ("unavailable", ConnectorUpgradeSigningProviderConformanceState.UNAVAILABLE),
        ("ineligible", ConnectorUpgradeSigningProviderConformanceState.INELIGIBLE_KEY),
        ("sign", ConnectorUpgradeSigningProviderConformanceState.SIGN_FAILED),
        ("verify", ConnectorUpgradeSigningProviderConformanceState.VERIFY_FAILED),
    ),
)
async def test_signing_provider_conformance_reports_stable_fail_closed_outcomes(
    provider_mode: str,
    expected: ConnectorUpgradeSigningProviderConformanceState,
) -> None:
    service, _, _, _, _, _, _, _ = await approval_fixture()
    if provider_mode == "unavailable":
        service._evidence_authenticity_provider = UnavailableUpgradeEvidenceAuthenticityProvider()
    else:
        service._evidence_authenticity_provider = _FailingConformanceProvider(
            service._evidence_authenticity_provider, provider_mode
        )
    assessment = await service.assess_signing_provider_conformance(
        actor=instance_operator(f"subject.connector-conformance-{provider_mode}"),
        acknowledged_diagnostic_grants_no_key_receipt_or_execution_authority=True,
        idempotency_key=f"connector-conformance-{provider_mode}",
        correlation_id=f"correlation.connector-conformance-{provider_mode}",
    )

    assert assessment.state is expected
    assert not assessment.signing_provider_conformant
    assert not assessment.execution_authorized


def test_signing_provider_conformance_api_requires_csrf_and_exposes_no_signature(
    tmp_path: Path,
) -> None:
    (
        service,
        _,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        _,
        _,
    ) = asyncio.run(approval_fixture())
    actor = instance_operator("subject.connector-conformance-api")
    app = create_app(
        settings(
            development_subject_id=actor.subject_id,
            mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
        ),
        identity_provider=BasicTestIdentityProvider(actor),
        registry_publication_service=publication_service,
        package_registration_service=registration_service,
        package_installation_service=package_service,
        connector_instance_creation_service=instance_service,
        connector_upgrade_approval_service=service,
    )
    endpoint = (
        "/api/v1/connectors/instances/upgrade-evidence-signing-provider-conformance-assessments"
    )
    body = {
        "schema_version": "atlas.connector-upgrade-signing-provider-conformance-input.v1",
        "acknowledged_diagnostic_grants_no_key_receipt_or_execution_authority": True,
    }
    with TestClient(app) as client:
        login_response = login(client)
        no_csrf = client.post(
            endpoint,
            headers={"Idempotency-Key": "connector-conformance-api-no-csrf"},
            json=body,
        )
        extra_input = client.post(
            endpoint,
            headers={
                "Idempotency-Key": "connector-conformance-api-extra",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
            json={**body, "payload_digest": "a" * 64},
        )
        created = client.post(
            endpoint,
            headers={
                "Idempotency-Key": "connector-conformance-api-created",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
            json=body,
        )
        latest = client.get(f"{endpoint}/latest")

    assert no_csrf.status_code == 403
    assert no_csrf.json()["code"] == "csrf_validation_failed"
    assert extra_input.status_code == 422
    assert created.status_code == 201
    assert created.headers["Cache-Control"] == "no-store"
    assert latest.status_code == 200
    assert latest.headers["Cache-Control"] == "no-store"
    payload = created.json()["data"]
    assert payload["state"] == "conformant"
    assert payload["diagnostic_only"] is True
    assert payload["receipt_signing_authorized"] is False
    assert payload["execution_authorized"] is False
    assert "signature" not in payload
    assert "signature_value" not in payload
    assert "key_material" not in payload


class _ProductionConformanceProvider:
    def __init__(self, *, key: ConnectorUpgradeEvidenceSigningKey) -> None:
        self._key = key

    async def trust_inventory(
        self, *, organization_id: str, environment_id: str
    ) -> ConnectorUpgradeEvidenceSigningProviderTrust:
        return ConnectorUpgradeEvidenceSigningProviderTrust(
            provider_class="provider.test-production-kms",
            organization_id=organization_id,
            environment_id=environment_id,
            provider_available=True,
            production_approved=True,
            keys=(self._key,),
        )

    async def active_key(
        self, *, organization_id: str, environment_id: str
    ) -> ConnectorUpgradeEvidenceSigningKey:
        assert organization_id == self._key.organization_id
        assert environment_id == self._key.environment_id
        return self._key

    async def diagnostic_sign_and_verify(
        self,
        *,
        organization_id: str,
        environment_id: str,
        challenge_digest: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> ConnectorUpgradeEvidenceSigningProviderDiagnostic:
        del challenge_digest, issued_at, expires_at
        return ConnectorUpgradeEvidenceSigningProviderDiagnostic(
            provider_class="provider.test-production-kms",
            organization_id=organization_id,
            environment_id=environment_id,
            key=self._key,
            state=ConnectorUpgradeSigningProviderConformanceState.CONFORMANT,
        )

    async def sign(
        self,
        *,
        key: ConnectorUpgradeEvidenceSigningKey,
        payload_digest: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> ConnectorUpgradeEvidenceSignature:
        raise ConnectorUpgradeEvidenceAuthenticityError("test_provider_sign_not_implemented")

    async def verify(
        self,
        *,
        signature: ConnectorUpgradeEvidenceSignature,
        payload_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorUpgradeEvidenceSigningKey:
        raise ConnectorUpgradeEvidenceAuthenticityError("test_provider_verify_not_implemented")


class _OnboardingEvidenceSource:
    def __init__(self, evidence: ConnectorUpgradeSigningProviderOnboardingEvidence | None) -> None:
        self._evidence = evidence

    async def get_current(
        self, *, organization_id: str, environment_id: str, provider_class: str
    ) -> ConnectorUpgradeSigningProviderOnboardingEvidence | None:
        del organization_id, environment_id, provider_class
        return self._evidence


@pytest.mark.asyncio
async def test_onboarding_readiness_blocks_nonproduction_and_missing_evidence() -> None:
    service, _, _, _, _, _, sources, audit = await approval_fixture()
    instance, _ = sources
    actor = instance_operator("subject.connector-onboarding-readiness-blocked")
    await service.assess_signing_provider_conformance(
        actor=actor,
        acknowledged_diagnostic_grants_no_key_receipt_or_execution_authority=True,
        idempotency_key="connector-onboarding-readiness-blocked",
        correlation_id="correlation.connector-onboarding-readiness-assess",
    )

    dossier = await service.signing_provider_onboarding_readiness(
        actor=actor,
        correlation_id="correlation.connector-onboarding-readiness-blocked",
    )

    states = {item.requirement_id: item.state for item in dossier.requirements}
    assert dossier.organization_id == instance.organization_id
    assert dossier.readiness_state == "blocked"
    assert not dossier.provider_onboarding_ready
    assert states["provider-available"] is (
        ConnectorUpgradeSigningProviderOnboardingRequirementState.SATISFIED
    )
    assert states["provider-production-approved"] is (
        ConnectorUpgradeSigningProviderOnboardingRequirementState.BLOCKED
    )
    assert states["production-algorithm-approved"] is (
        ConnectorUpgradeSigningProviderOnboardingRequirementState.BLOCKED
    )
    assert states["conformance-current"] is (
        ConnectorUpgradeSigningProviderOnboardingRequirementState.SATISFIED
    )
    assert "security-approval-current" in dossier.required_external_inputs
    assert dossier.evidence_only and not dossier.provider_configuration_authorized
    assert not dossier.key_management_authorized and not dossier.receipt_signing_authorized
    assert not dossier.execution_authorized and not dossier.infrastructure_mutation_performed
    assert audit.records[-1].result_code == (
        "connector_upgrade_signing_provider_onboarding_blocked"
    )


@pytest.mark.asyncio
async def test_signing_provider_onboarding_readiness_requires_all_authoritative_evidence() -> None:
    service, _, _, _, _, _, sources, audit = await approval_fixture()
    instance, _ = sources
    now = service._clock()
    key = ConnectorUpgradeEvidenceSigningKey(
        key_id="key.connector-upgrade-evidence.production-test",
        key_version="version.1",
        signer_profile_id="signer-profile.production-test",
        signer_workload_id="workload.connector-upgrade-evidence-production-test",
        algorithm="algorithm.rsassa-pss-sha256",
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        state=ConnectorUpgradeEvidenceSigningKeyState.ACTIVE,
        not_before=now - timedelta(hours=1),
        expires_at=now + timedelta(days=1),
    )
    service._evidence_authenticity_provider = _ProductionConformanceProvider(key=key)
    service._signing_provider_onboarding_evidence_source = _OnboardingEvidenceSource(
        ConnectorUpgradeSigningProviderOnboardingEvidence(
            organization_id=instance.organization_id,
            environment_id=instance.environment_id,
            provider_class="provider.test-production-kms",
            workload_identity_approved=True,
            secret_reference_ownership_verified=True,
            network_boundary_approved=True,
            key_lifecycle_and_revocation_approved=True,
            audit_routing_verified=True,
            availability_and_recovery_verified=True,
            security_approval_reference="approval.security.test",
            deployment_approval_reference="approval.deployment.test",
        )
    )
    actor = instance_operator("subject.connector-onboarding-readiness-ready")
    await service.assess_signing_provider_conformance(
        actor=actor,
        acknowledged_diagnostic_grants_no_key_receipt_or_execution_authority=True,
        idempotency_key="connector-onboarding-readiness-ready",
        correlation_id="correlation.connector-onboarding-readiness-ready-assess",
    )

    dossier = await service.signing_provider_onboarding_readiness(
        actor=actor,
        correlation_id="correlation.connector-onboarding-readiness-ready",
    )

    assert dossier.provider_onboarding_ready and dossier.readiness_state == "ready"
    assert dossier.policy_id.endswith(".development")
    assert dossier.policy_digest != "0" * 64
    assert dossier.policy_expires_at > dossier.evaluated_at
    assert dossier.policy_issued_by == "subject.security-architecture"
    assert dossier.policy_provenance_verified
    assert dossier.policy_attestation_id.startswith(
        "connector-upgrade-signing-provider-onboarding-policy-attestation."
    )
    assert dossier.policy_trust_key_id == ("key.connector-upgrade-onboarding-policy.nonproduction")
    assert dossier.required_external_inputs == ()
    assert all(
        item.state is ConnectorUpgradeSigningProviderOnboardingRequirementState.SATISFIED
        for item in dossier.requirements
    )
    assert not dossier.provider_configuration_authorized
    assert not dossier.execution_authorized
    assert audit.records[-1].result_code == "connector_upgrade_signing_provider_onboarding_ready"


class _OnboardingPolicySource:
    def __init__(
        self, policies: tuple[ConnectorUpgradeSigningProviderOnboardingPolicySnapshot, ...]
    ) -> None:
        self._policies = policies

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorUpgradeSigningProviderOnboardingPolicySnapshot, ...]:
        del organization_id, environment_id
        return self._policies


@pytest.mark.asyncio
async def test_onboarding_policy_fails_closed_for_missing_invalid_and_ambiguous() -> None:
    service, _, _, _, _, _, sources, _ = await approval_fixture()
    instance, _ = sources
    actor = instance_operator("subject.connector-onboarding-policy-governance")
    now = service._clock()

    service._signing_provider_onboarding_policy_source = None
    with pytest.raises(
        ConnectorUpgradeApprovalError,
        match="connector_upgrade_signing_provider_onboarding_policy_unavailable",
    ):
        await service.signing_provider_onboarding_readiness(
            actor=actor, correlation_id="correlation.onboarding-policy-unavailable"
        )

    expired = build_development_connector_upgrade_signing_provider_onboarding_policy(
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        issued_at=now - timedelta(days=2),
        expires_at=now - timedelta(days=1),
    )
    service._signing_provider_onboarding_policy_source = (
        InMemoryConnectorUpgradeSigningProviderOnboardingPolicySource((expired,))
    )
    with pytest.raises(
        ConnectorUpgradeApprovalError,
        match="connector_upgrade_signing_provider_onboarding_policy_expired",
    ):
        await service.signing_provider_onboarding_readiness(
            actor=actor, correlation_id="correlation.onboarding-policy-expired"
        )

    active = build_development_connector_upgrade_signing_provider_onboarding_policy(
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=1),
    )
    service._signing_provider_onboarding_policy_source = (
        InMemoryConnectorUpgradeSigningProviderOnboardingPolicySource((active, active))
    )
    with pytest.raises(
        ConnectorUpgradeApprovalError,
        match="connector_upgrade_signing_provider_onboarding_policy_ambiguous",
    ):
        await service.signing_provider_onboarding_readiness(
            actor=actor, correlation_id="correlation.onboarding-policy-ambiguous"
        )

    service._signing_provider_onboarding_policy_source = (
        InMemoryConnectorUpgradeSigningProviderOnboardingPolicySource(
            (replace(active, canonical_digest="f" * 64),)
        )
    )
    with pytest.raises(
        ConnectorUpgradeApprovalError,
        match="connector_upgrade_signing_provider_onboarding_policy_integrity_failed",
    ):
        await service.signing_provider_onboarding_readiness(
            actor=actor, correlation_id="correlation.onboarding-policy-integrity"
        )


@pytest.mark.asyncio
async def test_onboarding_policy_governance_rejects_source_scope_mismatch() -> None:
    service, _, _, _, _, _, sources, _ = await approval_fixture()
    instance, _ = sources
    now = service._clock()
    foreign = build_development_connector_upgrade_signing_provider_onboarding_policy(
        organization_id="organization.foreign",
        environment_id=instance.environment_id,
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=1),
    )
    service._signing_provider_onboarding_policy_source = _OnboardingPolicySource((foreign,))

    with pytest.raises(
        ConnectorUpgradeApprovalError,
        match="connector_upgrade_signing_provider_onboarding_policy_scope_invalid",
    ):
        await service.signing_provider_onboarding_readiness(
            actor=instance_operator("subject.connector-onboarding-policy-scope"),
            correlation_id="correlation.onboarding-policy-scope",
        )


class _RejectingOnboardingPolicyVerifier:
    async def verify(self, *, attestation: object, trust_key: object) -> bool:
        del attestation, trust_key
        return False


@pytest.mark.asyncio
async def test_onboarding_policy_provenance_fails_closed_without_attestation_or_trust() -> None:
    service, _, _, _, _, _, _, _ = await approval_fixture()
    actor = instance_operator("subject.connector-onboarding-policy-provenance-missing")
    service._signing_provider_onboarding_policy_attestation_source = (
        InMemoryConnectorUpgradeSigningProviderOnboardingPolicyAttestationSource()
    )
    with pytest.raises(
        ConnectorUpgradeApprovalError,
        match="connector_upgrade_signing_provider_onboarding_policy_attestation_unavailable",
    ):
        await service.signing_provider_onboarding_readiness(
            actor=actor, correlation_id="correlation.onboarding-policy-attestation-missing"
        )

    service, _, _, _, _, _, _, _ = await approval_fixture()
    service._signing_provider_onboarding_policy_trust_source = (
        InMemoryConnectorUpgradeSigningProviderOnboardingPolicyTrustSource()
    )
    with pytest.raises(
        ConnectorUpgradeApprovalError,
        match="connector_upgrade_signing_provider_onboarding_policy_trust_key_unavailable",
    ):
        await service.signing_provider_onboarding_readiness(
            actor=actor, correlation_id="correlation.onboarding-policy-trust-missing"
        )


@pytest.mark.asyncio
async def test_onboarding_policy_provenance_rejects_unverified_signature() -> None:
    service, _, _, _, _, _, _, _ = await approval_fixture()
    service._signing_provider_onboarding_policy_verifier = _RejectingOnboardingPolicyVerifier()
    with pytest.raises(
        ConnectorUpgradeApprovalError,
        match="connector_upgrade_signing_provider_onboarding_policy_signature_unverified",
    ):
        await service.signing_provider_onboarding_readiness(
            actor=instance_operator("subject.connector-onboarding-policy-signature"),
            correlation_id="correlation.onboarding-policy-signature",
        )


@pytest.mark.asyncio
async def test_onboarding_policy_provenance_diagnostic_is_scoped_audited_and_safe() -> None:
    service, _, _, _, _, _, sources, audit = await approval_fixture()
    instance, _ = sources
    diagnostic = await service.signing_provider_onboarding_policy_provenance_diagnostic(
        actor=instance_operator("subject.connector-onboarding-policy-diagnostic"),
        correlation_id="correlation.onboarding-policy-diagnostic",
    )

    assert (
        diagnostic.state is ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceState.VERIFIED
    )
    assert diagnostic.provenance_verified
    assert diagnostic.valid_until is not None
    assert tuple(check.check_id for check in diagnostic.checks) == (
        "policy-current",
        "attestation-current",
        "attestation-binding-valid",
        "trust-key-current",
        "signature-verified",
    )
    assert all(
        check.state is ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceCheckState.VERIFIED
        for check in diagnostic.checks
    )
    assert diagnostic.organization_id == instance.organization_id
    assert diagnostic.environment_id == instance.environment_id
    assert diagnostic.attestation_digest is not None
    assert not diagnostic.policy_authoring_authorized
    assert not diagnostic.trust_management_authorized
    assert not diagnostic.execution_authorized
    assert audit.records[-1].permission_id is not None
    assert audit.records[-1].permission_id.endswith("provenance-diagnostics.read")
    assert audit.records[-1].result_code.endswith("provenance_verified")


@pytest.mark.asyncio
async def test_onboarding_policy_provenance_diagnostic_explains_missing_and_unverified() -> None:
    service, _, _, _, _, _, _, _ = await approval_fixture()
    actor = instance_operator("subject.connector-onboarding-policy-diagnostic-blocked")
    service._signing_provider_onboarding_policy_attestation_source = (
        InMemoryConnectorUpgradeSigningProviderOnboardingPolicyAttestationSource()
    )
    missing = await service.signing_provider_onboarding_policy_provenance_diagnostic(
        actor=actor,
        correlation_id="correlation.onboarding-policy-diagnostic-missing",
    )

    assert missing.state is ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceState.BLOCKED
    assert not missing.provenance_verified
    assert missing.policy_id is not None
    assert missing.attestation_id is None
    assert missing.checks[0].state is (
        ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceCheckState.VERIFIED
    )
    assert missing.checks[1].state is (
        ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceCheckState.UNAVAILABLE
    )
    assert missing.reason_codes[0].endswith(".attestation-unavailable")
    with pytest.raises(
        ConnectorUpgradeApprovalError,
        match="connector_upgrade_signing_provider_onboarding_policy_attestation_unavailable",
    ):
        await service.signing_provider_onboarding_readiness(
            actor=actor,
            correlation_id="correlation.onboarding-policy-readiness-still-blocked",
        )

    service, _, _, _, _, _, _, _ = await approval_fixture()
    service._signing_provider_onboarding_policy_verifier = _RejectingOnboardingPolicyVerifier()
    unverified = await service.signing_provider_onboarding_policy_provenance_diagnostic(
        actor=actor,
        correlation_id="correlation.onboarding-policy-diagnostic-unverified",
    )
    assert unverified.checks[-1].state is (
        ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceCheckState.BLOCKED
    )
    assert unverified.reason_codes == (
        "connector.upgrade.signing-provider-onboarding-policy-provenance.signature-unverified",
    )


@pytest.mark.asyncio
async def test_onboarding_policy_provenance_diagnostic_explains_policy_lifecycle() -> None:
    service, _, _, _, _, _, sources, _ = await approval_fixture()
    instance, _ = sources
    actor = instance_operator("subject.connector-onboarding-policy-diagnostic-lifecycle")
    service._signing_provider_onboarding_policy_source = None
    unavailable = await service.signing_provider_onboarding_policy_provenance_diagnostic(
        actor=actor,
        correlation_id="correlation.onboarding-policy-diagnostic-unavailable",
    )
    assert unavailable.checks[0].state is (
        ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceCheckState.BLOCKED
    )
    assert unavailable.checks[0].reason_code.endswith(".unavailable")
    assert unavailable.policy_id is None
    assert all(
        check.state
        is ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceCheckState.UNAVAILABLE
        for check in unavailable.checks[1:]
    )

    now = service._clock()
    expired_policy = build_development_connector_upgrade_signing_provider_onboarding_policy(
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        issued_at=now - timedelta(days=2),
        expires_at=now - timedelta(days=1),
    )
    service._signing_provider_onboarding_policy_source = (
        InMemoryConnectorUpgradeSigningProviderOnboardingPolicySource((expired_policy,))
    )
    expired = await service.signing_provider_onboarding_policy_provenance_diagnostic(
        actor=actor,
        correlation_id="correlation.onboarding-policy-diagnostic-expired",
    )
    assert expired.checks[0].reason_code.endswith(".expired")
    assert expired.policy_id is None


def _trust_key_with_integrity(
    service: ConnectorUpgradeApprovalService,
    key: ConnectorUpgradeSigningProviderOnboardingPolicyTrustKey,
    **changes: object,
) -> ConnectorUpgradeSigningProviderOnboardingPolicyTrustKey:
    changed = replace(key, **cast(Any, changes), canonical_digest="0" * 64)
    payload = cast(dict[str, object], asdict(changed))
    payload.pop("canonical_digest")
    return replace(changed, canonical_digest=service._digest(service._normalize(payload)))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "expected_reason"),
    (
        (
            {"state": ConnectorUpgradeSigningProviderOnboardingPolicyTrustKeyState.DISABLED},
            "trust-key-disabled",
        ),
        (
            {"state": ConnectorUpgradeSigningProviderOnboardingPolicyTrustKeyState.REVOKED},
            "trust-key-revoked",
        ),
        (
            {
                "not_before": datetime(
                    2026, 7, 31, tzinfo=instance_operator().authenticated_at.tzinfo
                ),
                "expires_at": datetime(
                    2026, 8, 1, tzinfo=instance_operator().authenticated_at.tzinfo
                ),
            },
            "trust-key-expired",
        ),
        (
            {
                "not_before": datetime(
                    2026, 8, 20, tzinfo=instance_operator().authenticated_at.tzinfo
                ),
                "expires_at": datetime(
                    2026, 8, 21, tzinfo=instance_operator().authenticated_at.tzinfo
                ),
            },
            "trust-key-not-yet-effective",
        ),
    ),
)
async def test_onboarding_policy_provenance_diagnostic_reports_trust_lifecycle(
    changes: dict[str, object], expected_reason: str
) -> None:
    service, _, _, _, _, _, sources, _ = await approval_fixture()
    instance, _ = sources
    source = service._signing_provider_onboarding_policy_trust_source
    assert source is not None
    keys = await source.list_scope(
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        issuer_id="subject.security-architecture",
    )
    changed = _trust_key_with_integrity(service, keys[0], **changes)
    service._signing_provider_onboarding_policy_trust_source = (
        InMemoryConnectorUpgradeSigningProviderOnboardingPolicyTrustSource((changed,))
    )

    diagnostic = await service.signing_provider_onboarding_policy_provenance_diagnostic(
        actor=instance_operator("subject.connector-onboarding-policy-trust-lifecycle"),
        correlation_id="correlation.onboarding-policy-trust-lifecycle",
    )

    assert (
        diagnostic.state is ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceState.BLOCKED
    )
    assert diagnostic.checks[3].reason_code.endswith(expected_reason)
    assert diagnostic.checks[4].state is (
        ConnectorUpgradeSigningProviderOnboardingPolicyProvenanceCheckState.UNAVAILABLE
    )


@pytest.mark.asyncio
async def test_onboarding_policy_provenance_diagnostic_fails_closed_when_audit_fails() -> None:
    service, _, _, _, _, _, _, _ = await approval_fixture()
    service._audit_sink = FailingAuditSink()
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.signing_provider_onboarding_policy_provenance_diagnostic(
            actor=instance_operator("subject.connector-onboarding-policy-audit-failure"),
            correlation_id="correlation.onboarding-policy-audit-failure",
        )


@pytest.mark.asyncio
async def test_onboarding_readiness_rejects_stale_conformance_and_wrong_scope_evidence() -> None:
    service, _, _, _, _, _, sources, _ = await approval_fixture()
    instance, _ = sources
    actor = instance_operator("subject.connector-onboarding-readiness-stale")
    assessed_at = service._clock()
    await service.assess_signing_provider_conformance(
        actor=actor,
        acknowledged_diagnostic_grants_no_key_receipt_or_execution_authority=True,
        idempotency_key="connector-onboarding-readiness-stale",
        correlation_id="correlation.connector-onboarding-readiness-stale-assess",
    )
    service._clock = lambda: assessed_at + timedelta(minutes=6)

    stale = await service.signing_provider_onboarding_readiness(
        actor=actor,
        correlation_id="correlation.connector-onboarding-readiness-stale",
    )

    conformance = next(
        item for item in stale.requirements if item.requirement_id == "conformance-current"
    )
    assert conformance.state is ConnectorUpgradeSigningProviderOnboardingRequirementState.BLOCKED
    assert conformance.reason_code.endswith(".conformance-stale")

    service._signing_provider_onboarding_evidence_source = _OnboardingEvidenceSource(
        ConnectorUpgradeSigningProviderOnboardingEvidence(
            organization_id="organization.foreign",
            environment_id=instance.environment_id,
            provider_class="provider.nonproduction-hmac",
            workload_identity_approved=False,
            secret_reference_ownership_verified=False,
            network_boundary_approved=False,
            key_lifecycle_and_revocation_approved=False,
            audit_routing_verified=False,
            availability_and_recovery_verified=False,
            security_approval_reference=None,
            deployment_approval_reference=None,
        )
    )
    with pytest.raises(
        ConnectorUpgradeApprovalError,
        match="connector_upgrade_signing_provider_onboarding_evidence_not_found",
    ):
        await service.signing_provider_onboarding_readiness(
            actor=actor,
            correlation_id="correlation.connector-onboarding-readiness-wrong-scope",
        )


def test_signing_provider_onboarding_readiness_api_is_no_store_and_exact_schema(
    tmp_path: Path,
) -> None:
    (
        service,
        _,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        _,
        _,
    ) = asyncio.run(approval_fixture())
    actor = instance_operator("subject.connector-onboarding-readiness-api")
    app = create_app(
        settings(
            development_subject_id=actor.subject_id,
            mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
        ),
        identity_provider=BasicTestIdentityProvider(actor),
        registry_publication_service=publication_service,
        package_registration_service=registration_service,
        package_installation_service=package_service,
        connector_instance_creation_service=instance_service,
        connector_upgrade_approval_service=service,
    )
    endpoint = "/api/v1/connectors/instances/upgrade-evidence-signing-provider-onboarding-readiness"
    with TestClient(app) as client:
        login(client)
        response = client.get(endpoint)
        diagnostic_response = client.get(
            "/api/v1/connectors/instances/"
            "upgrade-evidence-signing-provider-onboarding-policy-provenance-diagnostic"
        )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    payload = response.json()["data"]
    assert payload["schema_version"] == (
        "atlas.connector-upgrade-signing-provider-onboarding-readiness.v1"
    )
    assert payload["readiness_state"] == "blocked"
    assert payload["provider_onboarding_ready"] is False
    assert payload["policy_id"].endswith(".development")
    assert len(payload["policy_digest"]) == 64
    assert payload["policy_issued_by"] == "subject.security-architecture"
    assert payload["policy_expires_at"] > payload["evaluated_at"]
    assert payload["policy_provenance_verified"] is True
    assert len(payload["policy_attestation_digest"]) == 64
    assert payload["policy_trust_key_id"].endswith(".nonproduction")
    assert payload["provider_configuration_authorized"] is False
    assert payload["execution_authorized"] is False
    assert "endpoint" not in payload
    assert "credential" not in payload
    assert "secret" not in payload
    assert "signature" not in payload
    assert "key_material" not in payload

    assert diagnostic_response.status_code == 200
    assert diagnostic_response.headers["Cache-Control"] == "no-store"
    diagnostic = diagnostic_response.json()["data"]
    assert diagnostic["schema_version"] == (
        "atlas.connector-upgrade-signing-provider-onboarding-policy-provenance-diagnostic.v1"
    )
    assert diagnostic["state"] == "verified"
    assert diagnostic["provenance_verified"] is True
    assert len(diagnostic["checks"]) == 5
    assert diagnostic["reason_codes"] == []
    assert diagnostic["trust_management_authorized"] is False
    assert diagnostic["execution_authorized"] is False
    assert "signature" not in diagnostic
    assert "key_material" not in diagnostic
    assert "credential" not in diagnostic
    assert "endpoint" not in diagnostic


def test_signing_key_trust_effective_state_precedence_is_deterministic() -> None:
    now = datetime(2026, 8, 12, 12, 0, tzinfo=instance_operator().authenticated_at.tzinfo)
    base = ConnectorUpgradeEvidenceSigningKey(
        key_id="key.connector-upgrade-evidence.state-test",
        key_version="version.1",
        signer_profile_id="signer-profile.nonproduction-hmac",
        signer_workload_id="workload.connector-upgrade-evidence-signer",
        algorithm="algorithm.hmac-sha256-nonproduction",
        organization_id="organization.development",
        environment_id="environment.development",
        state=ConnectorUpgradeEvidenceSigningKeyState.ACTIVE,
        not_before=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=1),
    )
    cases = (
        (base, ConnectorUpgradeEvidenceSigningKeyEffectiveState.ACTIVE),
        (
            replace(base, not_before=now + timedelta(hours=1), expires_at=now + timedelta(hours=2)),
            ConnectorUpgradeEvidenceSigningKeyEffectiveState.NOT_YET_VALID,
        ),
        (
            replace(base, not_before=now - timedelta(hours=2), expires_at=now),
            ConnectorUpgradeEvidenceSigningKeyEffectiveState.EXPIRED,
        ),
        (
            replace(base, state=ConnectorUpgradeEvidenceSigningKeyState.DISABLED),
            ConnectorUpgradeEvidenceSigningKeyEffectiveState.DISABLED,
        ),
        (
            replace(base, state=ConnectorUpgradeEvidenceSigningKeyState.REVOKED),
            ConnectorUpgradeEvidenceSigningKeyEffectiveState.REVOKED,
        ),
    )
    for source, expected in cases:
        trust = ConnectorUpgradeApprovalService._signing_key_trust(key=source, now=now)
        assert trust.effective_state is expected
        assert trust.signing_eligible is (
            expected is ConnectorUpgradeEvidenceSigningKeyEffectiveState.ACTIVE
        )
        assert trust.verification_trusted is trust.signing_eligible

    historical_verification = ConnectorUpgradeEvidenceSigningKeyTrust(
        key_id=base.key_id,
        key_version=base.key_version,
        signer_profile_id=base.signer_profile_id,
        signer_workload_id=base.signer_workload_id,
        algorithm=base.algorithm,
        configured_state=base.state,
        effective_state=ConnectorUpgradeEvidenceSigningKeyEffectiveState.EXPIRED,
        not_before=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
        signing_eligible=False,
        verification_trusted=True,
        reason_codes=("connector.upgrade.signing-key-trust.expired",),
    )
    assert not historical_verification.signing_eligible
    assert historical_verification.verification_trusted


@pytest.mark.asyncio
async def test_upgrade_approval_request_binds_exact_plan_without_granting_authority() -> None:
    service, upgrade_service, _, _, _, _, sources, audit = await approval_fixture()
    instance, candidate_receipt = sources
    actor = instance_operator()
    plan = await upgrade_service.plan(
        actor=actor,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-plan-source",
    )

    request = await service.create(
        actor=actor,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        source_plan_digest=plan.canonical_digest,
        purpose="Submit this exact connector upgrade plan for independent human review.",
        acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
        idempotency_key="connector-upgrade-approval-001",
        correlation_id="correlation.connector-upgrade-approval",
    )
    replay = await service.create(
        actor=actor,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        source_plan_digest=plan.canonical_digest,
        purpose="Submit this exact connector upgrade plan for independent human review.",
        acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
        idempotency_key="connector-upgrade-approval-001",
        correlation_id="correlation.connector-upgrade-approval-replay",
    )

    assert request.plan_id == plan.plan_id and request.plan_digest == plan.canonical_digest
    assert request.candidate_receipt_digest == plan.candidate_receipt_digest
    assert request.state == "pending" and request.separation_of_duties_required
    assert not request.approval_granted and not request.decision_recorded
    assert not request.execution_authorized and not request.infrastructure_mutation_performed
    assert request.requested_by == actor.subject_id
    assert replay.request_id == request.request_id and replay.reused
    restored = PostgreSQLConnectorUpgradeApprovalRepository._to_domain(
        cast(
            dict[str, object],
            ConnectorUpgradeApprovalService._normalize(asdict(request)),
        )
    )
    assert restored == request
    assert [item.result_code for item in audit.records].count(
        "connector_upgrade_approval_request_created"
    ) == 1


@pytest.mark.asyncio
async def test_upgrade_approval_request_fails_closed_for_drift_and_configured_target() -> None:
    service, _upgrade_service, _, _, _, _, sources, _ = await approval_fixture()
    instance, candidate_receipt = sources
    actor = instance_operator()
    with pytest.raises(ConnectorUpgradeApprovalError, match="plan_not_eligible"):
        await service.create(
            actor=actor,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            source_plan_digest="0" * 64,
            purpose="Submit this exact connector upgrade plan for independent human review.",
            acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-approval-drift",
            correlation_id="correlation.connector-upgrade-approval-drift",
        )

    (
        target_service,
        configured_instance_service,
        package_service,
        _,
        configured_instance,
        profile,
        target_policy,
    ) = await target_configuration_fixture()
    await bind_target(target_service, configured_instance, profile, target_policy)
    (
        current_receipt,
        _,
        current_registration,
        _,
    ) = await package_service.connector_instance_creation_source(
        receipt_id=configured_instance.source_installation_receipt_id
    )
    configured_candidate, configured_registration = upgrade_package(
        current_receipt, current_registration
    )
    configured_upgrade_service = ConnectorUpgradeReadinessService(
        instance_repository=configured_instance_service.repository,
        target_repository=target_service.repository,
        package_source=UpgradePackageSource(
            (
                (current_receipt, current_registration),
                (configured_candidate, configured_registration),
            )
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=configured_instance.environment_id,
    )
    blocked_plan = await configured_upgrade_service.plan(
        actor=actor,
        record_id=configured_instance.record_id,
        candidate_receipt_id=configured_candidate.receipt_id,
        correlation_id="correlation.connector-upgrade-plan-blocked",
    )
    blocked_service = ConnectorUpgradeApprovalService(
        repository=InMemoryConnectorUpgradeApprovalRepository(),
        policy_source=InMemoryConnectorUpgradeApprovalPolicySource(()),
        upgrade_service=configured_upgrade_service,
        audit_sink=CollectingAuditSink(),
        environment_id=configured_instance.environment_id,
    )
    with pytest.raises(ConnectorUpgradeApprovalError, match="plan_not_eligible"):
        await blocked_service.create(
            actor=actor,
            record_id=configured_instance.record_id,
            candidate_receipt_id=configured_candidate.receipt_id,
            source_plan_digest=blocked_plan.canonical_digest,
            purpose="Submit this exact connector upgrade plan for independent human review.",
            acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-approval-blocked",
            correlation_id="correlation.connector-upgrade-approval-blocked",
        )


def test_upgrade_approval_api_is_no_store_and_hides_custody_metadata(tmp_path: Path) -> None:
    (
        approval_service,
        upgrade_service,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        sources,
        _,
    ) = asyncio.run(approval_fixture())
    instance, candidate_receipt = sources
    actor = instance_operator()
    plan = asyncio.run(
        upgrade_service.plan(
            actor=actor,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            correlation_id="correlation.connector-upgrade-plan-api",
        )
    )
    app = create_app(
        settings(
            development_subject_id=actor.subject_id,
            mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
        ),
        identity_provider=BasicTestIdentityProvider(actor),
        registry_publication_service=publication_service,
        package_registration_service=registration_service,
        package_installation_service=package_service,
        connector_instance_creation_service=instance_service,
        connector_upgrade_approval_service=approval_service,
    )
    with TestClient(app) as client:
        app.state.connector_upgrade_readiness_service = upgrade_service
        login_response = login(client)
        response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-plans/"
            f"{candidate_receipt.receipt_id}/approval-requests",
            headers={
                "Idempotency-Key": "connector-upgrade-approval-api",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
            json={
                "schema_version": "atlas.connector-upgrade-approval-create-input.v1",
                "source_plan_digest": plan.canonical_digest,
                "purpose": "Submit this exact connector upgrade plan for independent human review.",
                "acknowledged_request_is_not_approval_and_grants_no_execution_authority": True,
            },
        )
        assert response.status_code == 201, response.text
        request_id = response.json()["data"]["request_id"]
        read_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request_id}"
        )

    assert response.headers["Cache-Control"] == "no-store"
    assert read_response.status_code == 200 and read_response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["plan_digest"] == plan.canonical_digest and data["state"] == "pending"
    assert data["approval_granted"] is False and data["execution_authorized"] is False
    rendered = response.text.lower()
    for hidden in ("request_fingerprint", "idempotency_key", "credential", "target_endpoint"):
        assert hidden not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "state", "valid"),
    (
        (ConnectorUpgradeApprovalOutcome.APPROVE, ConnectorUpgradeApprovalState.APPROVED, True),
        (ConnectorUpgradeApprovalOutcome.REJECT, ConnectorUpgradeApprovalState.REJECTED, False),
        (
            ConnectorUpgradeApprovalOutcome.NEEDS_EVIDENCE,
            ConnectorUpgradeApprovalState.NEEDS_EVIDENCE,
            False,
        ),
        (ConnectorUpgradeApprovalOutcome.DEFER, ConnectorUpgradeApprovalState.DEFERRED, False),
    ),
)
async def test_upgrade_approval_decision_is_separated_exact_and_non_executable(
    outcome: ConnectorUpgradeApprovalOutcome,
    state: ConnectorUpgradeApprovalState,
    valid: bool,
) -> None:
    service, upgrade_service, _, _, _, _, sources, audit = await approval_fixture()
    instance, candidate_receipt = sources
    requester = instance_operator()
    approver = instance_operator("subject.connector-upgrade-independent-approver")
    plan = await upgrade_service.plan(
        actor=requester,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-decision-plan",
    )
    request = await service.create(
        actor=requester,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        source_plan_digest=plan.canonical_digest,
        purpose="Submit this exact connector upgrade plan for independent human review.",
        acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
        idempotency_key=f"connector-upgrade-request-{outcome.value}",
        correlation_id="correlation.connector-upgrade-decision-request",
    )
    with pytest.raises(ConnectorUpgradeApprovalError, match="separation_required"):
        await service.decide(
            actor=requester,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_request_version=request.version,
            expected_request_digest=request.canonical_digest,
            outcome=outcome,
            rationale="Record an accountable decision after reviewing the exact immutable plan.",
            acknowledged_decision_grants_no_execution_authority=True,
            idempotency_key=f"connector-upgrade-decision-self-{outcome.value}",
            correlation_id="correlation.connector-upgrade-decision-self",
        )

    record = await service.decide(
        actor=approver,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_request_version=request.version,
        expected_request_digest=request.canonical_digest,
        outcome=outcome,
        rationale="Record an accountable decision after reviewing the exact immutable plan.",
        acknowledged_decision_grants_no_execution_authority=True,
        idempotency_key=f"connector-upgrade-decision-{outcome.value}",
        correlation_id="correlation.connector-upgrade-decision",
    )
    replay = await service.decide(
        actor=approver,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_request_version=request.version,
        expected_request_digest=request.canonical_digest,
        outcome=outcome,
        rationale="Record an accountable decision after reviewing the exact immutable plan.",
        acknowledged_decision_grants_no_execution_authority=True,
        idempotency_key=f"connector-upgrade-decision-{outcome.value}",
        correlation_id="correlation.connector-upgrade-decision-replay",
    )

    assert record.state is state and record.approval_valid is valid
    assert record.approval_granted is valid and record.decision_recorded
    assert record.decision is not None and record.decision.decided_by == approver.subject_id
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert replay.decision is not None and replay.decision.reused
    restored = PostgreSQLConnectorUpgradeApprovalRepository._decision_to_domain(
        cast(
            dict[str, object],
            ConnectorUpgradeApprovalService._normalize(asdict(record.decision)),
        )
    )
    assert restored == record.decision
    assert [item.result_code for item in audit.records].count(
        f"connector_upgrade_approval_{outcome.value}"
    ) == 1


def test_upgrade_approval_decision_api_restores_plan_record_and_hides_authority(
    tmp_path: Path,
) -> None:
    (
        approval_service,
        upgrade_service,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        sources,
        _,
    ) = asyncio.run(approval_fixture())
    instance, candidate_receipt = sources
    requester = instance_operator()
    approver = instance_operator("subject.connector-upgrade-independent-approver")
    plan = asyncio.run(
        upgrade_service.plan(
            actor=requester,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            correlation_id="correlation.connector-upgrade-decision-api-plan",
        )
    )
    approval_request = asyncio.run(
        approval_service.create(
            actor=requester,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            source_plan_digest=plan.canonical_digest,
            purpose="Submit this exact connector upgrade plan for independent human review.",
            acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-decision-api-request",
            correlation_id="correlation.connector-upgrade-decision-api-request",
        )
    )
    app = create_app(
        settings(
            development_subject_id=approver.subject_id,
            mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
        ),
        identity_provider=BasicTestIdentityProvider(approver),
        registry_publication_service=publication_service,
        package_registration_service=registration_service,
        package_installation_service=package_service,
        connector_instance_creation_service=instance_service,
        connector_upgrade_approval_service=approval_service,
    )
    with TestClient(app) as client:
        app.state.connector_upgrade_readiness_service = upgrade_service
        login_response = login(client)
        read_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-plans/"
            f"{candidate_receipt.receipt_id}/approval-record"
        )
        response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{approval_request.request_id}/decisions",
            headers={
                "Idempotency-Key": "connector-upgrade-decision-api",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
            json={
                "schema_version": "atlas.connector-upgrade-approval-decision-input.v1",
                "expected_request_version": approval_request.version,
                "expected_request_digest": approval_request.canonical_digest,
                "outcome": "approve",
                "rationale": "Approve the exact immutable plan after independent evidence review.",
                "acknowledged_decision_grants_no_execution_authority": True,
            },
        )

    assert read_response.status_code == 200
    assert read_response.json()["data"]["state"] == "pending"
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["state"] == "approved" and data["approval_valid"] is True
    assert data["execution_authorized"] is False
    rendered = response.text.lower()
    for hidden in (
        "request_fingerprint",
        "decision_fingerprint",
        "idempotency_key",
        "credential",
        "target_endpoint",
    ):
        assert hidden not in rendered


@pytest.mark.asyncio
async def test_upgrade_approval_revalidation_requires_three_people_and_remains_non_executable() -> (
    None
):
    current_time: list[datetime] = []

    def clock() -> datetime:
        return current_time[0]

    bootstrap = await instance_fixture()
    current_time.append(bootstrap[4].installed_at + timedelta(hours=2))
    audit_readiness_source = InMemoryConnectorUpgradeAuditReadinessSource()
    itsm_change_evidence_source = InMemoryConnectorUpgradeItsmChangeEvidenceSource()
    maintenance_window_evidence_source = InMemoryConnectorUpgradeMaintenanceWindowEvidenceSource()
    service, upgrade_service, _, _, _, _, sources, audit = await approval_fixture(
        clock=clock,
        audit_readiness_source=audit_readiness_source,
        itsm_change_evidence_source=itsm_change_evidence_source,
        maintenance_window_evidence_source=maintenance_window_evidence_source,
    )
    instance, candidate_receipt = sources
    requester = instance_operator()
    approver = instance_operator("subject.connector-upgrade-independent-approver")
    verifier = instance_operator("subject.connector-upgrade-independent-verifier")
    plan = await upgrade_service.plan(
        actor=requester,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-revalidation-plan",
    )
    request = await service.create(
        actor=requester,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        source_plan_digest=plan.canonical_digest,
        purpose="Submit this exact connector upgrade plan for independent human review.",
        acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
        idempotency_key="connector-upgrade-revalidation-request",
        correlation_id="correlation.connector-upgrade-revalidation-request",
    )
    current_time[0] += timedelta(minutes=5)
    record = await service.decide(
        actor=approver,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_request_version=request.version,
        expected_request_digest=request.canonical_digest,
        outcome=ConnectorUpgradeApprovalOutcome.APPROVE,
        rationale="Approve the unchanged plan after independent evidence review.",
        acknowledged_decision_grants_no_execution_authority=True,
        idempotency_key="connector-upgrade-revalidation-decision",
        correlation_id="correlation.connector-upgrade-revalidation-decision",
    )
    assert record.decision is not None
    current_time[0] += timedelta(minutes=5)

    for actor in (requester, approver):
        with pytest.raises(ConnectorUpgradeApprovalError, match="separation_required"):
            await service.revalidate(
                actor=actor,
                record_id=instance.record_id,
                request_id=request.request_id,
                expected_request_digest=request.canonical_digest,
                expected_decision_digest=record.decision.canonical_digest,
                purpose="Revalidate the exact approved plan without granting handoff authority.",
                acknowledged_revalidation_grants_no_handoff_or_execution_authority=True,
                idempotency_key=f"connector-upgrade-revalidation-self-{actor.subject_id[-8:]}",
                correlation_id="correlation.connector-upgrade-revalidation-self",
            )

    revalidation = await service.revalidate(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_request_digest=request.canonical_digest,
        expected_decision_digest=record.decision.canonical_digest,
        purpose="Revalidate the exact approved plan without granting handoff authority.",
        acknowledged_revalidation_grants_no_handoff_or_execution_authority=True,
        idempotency_key="connector-upgrade-revalidation-001",
        correlation_id="correlation.connector-upgrade-revalidation",
    )
    replay = await service.revalidate(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_request_digest=request.canonical_digest,
        expected_decision_digest=record.decision.canonical_digest,
        purpose="Revalidate the exact approved plan without granting handoff authority.",
        acknowledged_revalidation_grants_no_handoff_or_execution_authority=True,
        idempotency_key="connector-upgrade-revalidation-001",
        correlation_id="correlation.connector-upgrade-revalidation-replay",
    )
    latest = await service.get_latest_revalidation(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        correlation_id="correlation.connector-upgrade-revalidation-read",
    )
    readiness = await service.assess_handoff_readiness(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        correlation_id="correlation.connector-upgrade-handoff-readiness",
    )
    audit_evidence_payload = {
        "schema_version": "atlas.connector-upgrade-audit-readiness-evidence.v1",
        "organization_id": instance.organization_id,
        "environment_id": instance.environment_id,
        "request_id": request.request_id,
        "request_digest": request.canonical_digest,
        "revalidation_id": revalidation.revalidation_id,
        "revalidation_digest": revalidation.canonical_digest,
        "ledger_id": "audit-ledger.primary",
        "ledger_generation": "generation.2026-08-12",
        "producer_coverage_digest": "1" * 64,
        "integrity_verification_digest": "2" * 64,
        "redaction_policy_digest": "3" * 64,
        "retention_policy_digest": "4" * 64,
        "verified_at": current_time[0].isoformat(),
        "valid_until": (current_time[0] + timedelta(minutes=10)).isoformat(),
        "durable_acceptance": True,
        "append_only": True,
        "integrity_verified": True,
        "gap_free": True,
        "redaction_current": True,
        "retention_current": True,
        "producer_coverage_complete": True,
        "consequential_blocking_enabled": True,
        "infrastructure_mutation_performed": False,
    }
    audit_evidence_digest = ConnectorUpgradeApprovalService._digest(audit_evidence_payload)
    audit_evidence = ConnectorUpgradeAuditReadinessEvidence(
        evidence_id=f"connector-upgrade-audit-readiness-evidence.{audit_evidence_digest[:24]}",
        schema_version="atlas.connector-upgrade-audit-readiness-evidence.v1",
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        request_id=request.request_id,
        request_digest=request.canonical_digest,
        revalidation_id=revalidation.revalidation_id,
        revalidation_digest=revalidation.canonical_digest,
        ledger_id="audit-ledger.primary",
        ledger_generation="generation.2026-08-12",
        producer_coverage_digest="1" * 64,
        integrity_verification_digest="2" * 64,
        redaction_policy_digest="3" * 64,
        retention_policy_digest="4" * 64,
        verified_at=current_time[0],
        valid_until=current_time[0] + timedelta(minutes=10),
        canonical_digest=audit_evidence_digest,
        durable_acceptance=True,
        append_only=True,
        integrity_verified=True,
        gap_free=True,
        redaction_current=True,
        retention_current=True,
        producer_coverage_complete=True,
        consequential_blocking_enabled=True,
    )
    itsm_evidence_payload = {
        "schema_version": "atlas.connector-upgrade-itsm-change-evidence.v1",
        "organization_id": instance.organization_id,
        "environment_id": instance.environment_id,
        "request_id": request.request_id,
        "request_digest": request.canonical_digest,
        "revalidation_id": revalidation.revalidation_id,
        "revalidation_digest": revalidation.canonical_digest,
        "plan_id": plan.plan_id,
        "plan_digest": plan.canonical_digest,
        "adapter_id": "itsm-adapter.validated",
        "adapter_version": "version.1.0.0",
        "authoritative_instance_id": "itsm-instance.enterprise",
        "external_record_id": "change-record.chg000154",
        "external_record_version": "version.42",
        "observed_at": current_time[0].isoformat(),
        "valid_until": (current_time[0] + timedelta(minutes=8)).isoformat(),
        "adapter_validated": True,
        "authoritative_source": True,
        "record_accessible": True,
        "source_version_current": True,
        "exact_plan_binding_verified": True,
        "record_active": True,
        "conflict_free": True,
        "revocation_absent": True,
        "external_record_modified": False,
        "infrastructure_mutation_performed": False,
    }
    itsm_evidence_digest = ConnectorUpgradeApprovalService._digest(itsm_evidence_payload)
    itsm_evidence = ConnectorUpgradeItsmChangeEvidence(
        evidence_id=f"connector-upgrade-itsm-change-evidence.{itsm_evidence_digest[:24]}",
        schema_version="atlas.connector-upgrade-itsm-change-evidence.v1",
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        request_id=request.request_id,
        request_digest=request.canonical_digest,
        revalidation_id=revalidation.revalidation_id,
        revalidation_digest=revalidation.canonical_digest,
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        adapter_id="itsm-adapter.validated",
        adapter_version="version.1.0.0",
        authoritative_instance_id="itsm-instance.enterprise",
        external_record_id="change-record.chg000154",
        external_record_version="version.42",
        observed_at=current_time[0],
        valid_until=current_time[0] + timedelta(minutes=8),
        canonical_digest=itsm_evidence_digest,
        adapter_validated=True,
        authoritative_source=True,
        record_accessible=True,
        source_version_current=True,
        exact_plan_binding_verified=True,
        record_active=True,
        conflict_free=True,
        revocation_absent=True,
    )
    window_evidence_payload = {
        "schema_version": "atlas.connector-upgrade-maintenance-window-evidence.v1",
        "organization_id": instance.organization_id,
        "environment_id": instance.environment_id,
        "request_id": request.request_id,
        "request_digest": request.canonical_digest,
        "revalidation_id": revalidation.revalidation_id,
        "revalidation_digest": revalidation.canonical_digest,
        "plan_id": plan.plan_id,
        "plan_digest": plan.canonical_digest,
        "itsm_change_evidence_id": itsm_evidence.evidence_id,
        "itsm_change_evidence_digest": itsm_evidence.canonical_digest,
        "external_record_version": itsm_evidence.external_record_version,
        "window_version": "window-version.7",
        "approved_start": (current_time[0] - timedelta(minutes=5)).isoformat(),
        "approved_end": (current_time[0] + timedelta(minutes=6)).isoformat(),
        "observed_at": current_time[0].isoformat(),
        "valid_until": (current_time[0] + timedelta(minutes=5)).isoformat(),
        "authoritative_source": True,
        "window_approved": True,
        "source_version_current": True,
        "exact_change_binding_verified": True,
        "exact_plan_binding_verified": True,
        "inside_approved_window": True,
        "freeze_clear": True,
        "conflict_free": True,
        "revocation_absent": True,
        "external_record_modified": False,
        "infrastructure_mutation_performed": False,
    }
    window_evidence_digest = ConnectorUpgradeApprovalService._digest(window_evidence_payload)
    window_evidence = ConnectorUpgradeMaintenanceWindowEvidence(
        evidence_id=(
            f"connector-upgrade-maintenance-window-evidence.{window_evidence_digest[:24]}"
        ),
        schema_version="atlas.connector-upgrade-maintenance-window-evidence.v1",
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        request_id=request.request_id,
        request_digest=request.canonical_digest,
        revalidation_id=revalidation.revalidation_id,
        revalidation_digest=revalidation.canonical_digest,
        plan_id=plan.plan_id,
        plan_digest=plan.canonical_digest,
        itsm_change_evidence_id=itsm_evidence.evidence_id,
        itsm_change_evidence_digest=itsm_evidence.canonical_digest,
        external_record_version=itsm_evidence.external_record_version,
        window_version="window-version.7",
        approved_start=current_time[0] - timedelta(minutes=5),
        approved_end=current_time[0] + timedelta(minutes=6),
        observed_at=current_time[0],
        valid_until=current_time[0] + timedelta(minutes=5),
        canonical_digest=window_evidence_digest,
        authoritative_source=True,
        window_approved=True,
        source_version_current=True,
        exact_change_binding_verified=True,
        exact_plan_binding_verified=True,
        inside_approved_window=True,
        freeze_clear=True,
        conflict_free=True,
        revocation_absent=True,
    )
    draft = await service.create_change_context_draft(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_readiness_digest=readiness.canonical_digest,
        proposed_window_start=current_time[0] + timedelta(hours=2),
        proposed_window_end=current_time[0] + timedelta(hours=3),
        justification="Prepare a governed connector upgrade change-context draft for ITSM review.",
        acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority=True,
        idempotency_key="connector-upgrade-change-context-001",
        correlation_id="correlation.connector-upgrade-change-context",
    )
    replayed_draft = await service.create_change_context_draft(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_readiness_digest=readiness.canonical_digest,
        proposed_window_start=current_time[0] + timedelta(hours=2),
        proposed_window_end=current_time[0] + timedelta(hours=3),
        justification="Prepare a governed connector upgrade change-context draft for ITSM review.",
        acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority=True,
        idempotency_key="connector-upgrade-change-context-001",
        correlation_id="correlation.connector-upgrade-change-context-replay",
    )
    latest_draft = await service.get_latest_change_context_draft(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        correlation_id="correlation.connector-upgrade-change-context-read",
    )
    with pytest.raises(ConnectorUpgradeApprovalError, match="verifier_required"):
        await service.create_change_context_draft(
            actor=requester,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_readiness_digest=readiness.canonical_digest,
            proposed_window_start=current_time[0] + timedelta(hours=2),
            proposed_window_end=current_time[0] + timedelta(hours=3),
            justification="Prepare a governed connector upgrade change-context draft for review.",
            acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority=True,
            idempotency_key="connector-upgrade-change-context-requester",
            correlation_id="correlation.connector-upgrade-change-context-requester",
        )
    with pytest.raises(ConnectorUpgradeApprovalError, match="readiness_stale"):
        await service.create_change_context_draft(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_readiness_digest="0" * 64,
            proposed_window_start=current_time[0] + timedelta(hours=2),
            proposed_window_end=current_time[0] + timedelta(hours=3),
            justification="Prepare a governed connector upgrade change-context draft for review.",
            acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority=True,
            idempotency_key="connector-upgrade-change-context-stale",
            correlation_id="correlation.connector-upgrade-change-context-stale",
        )
    with pytest.raises(ConnectorUpgradeApprovalError, match="idempotency_conflict"):
        await service.create_change_context_draft(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_readiness_digest=readiness.canonical_digest,
            proposed_window_start=current_time[0] + timedelta(hours=3),
            proposed_window_end=current_time[0] + timedelta(hours=4),
            justification="Prepare a governed connector upgrade change-context draft for review.",
            acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority=True,
            idempotency_key="connector-upgrade-change-context-001",
            correlation_id="correlation.connector-upgrade-change-context-conflict",
        )

    assert revalidation.approval_current_at_revalidation
    assert revalidation.governance_ready and not revalidation.handoff_ready
    assert not revalidation.target_configured and not revalidation.package_rebound
    assert not revalidation.configuration_changed and not revalidation.target_contacted
    assert not revalidation.handoff_artifact_issued
    assert not revalidation.execution_authorized
    assert not revalidation.infrastructure_mutation_performed
    assert len(revalidation.check_ids) == 7
    assert replay.reused and latest.revalidation_id == revalidation.revalidation_id
    assert readiness.assessment_state == "blocked"
    assert readiness.applicability_policy_id == (
        "connector-upgrade-handoff-evidence-applicability.default"
    )
    assert readiness.applicability_policy_version == "v2026.08.12.1"
    assert len(readiness.required_check_ids) == 9
    assert len(readiness.satisfied_check_ids) == 6
    assert readiness.not_applicable_check_ids == (
        "connector.upgrade.handoff.target-binding-current",
        "connector.upgrade.handoff.service-impact-evidence-current",
        "connector.upgrade.handoff.runtime-health-evidence-current",
    )
    assert readiness.blocker_ids == (
        "connector.upgrade.handoff.blocked.itsm-change-missing",
        "connector.upgrade.handoff.blocked.maintenance-window-missing",
        "connector.upgrade.handoff.blocked.audit-readiness-evidence-missing",
    )
    assert readiness.audit_readiness_evidence_id is None
    assert not readiness.audit_readiness_evidence_current
    assert readiness.itsm_change_evidence_id is None
    assert not readiness.itsm_change_evidence_current
    assert readiness.maintenance_window_evidence_id is None
    assert not readiness.maintenance_window_evidence_current
    with pytest.raises(ConnectorUpgradeApprovalError, match="confirmation_required"):
        await service.create_evidence_receipt(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_readiness_digest=readiness.canonical_digest,
            acknowledged_receipt_is_non_executable_and_grants_no_handoff_authority=False,
            correlation_id="correlation.connector-upgrade-evidence-receipt-unconfirmed",
        )
    with pytest.raises(ConnectorUpgradeApprovalError, match="readiness_not_current"):
        await service.create_evidence_receipt(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_readiness_digest=readiness.canonical_digest,
            acknowledged_receipt_is_non_executable_and_grants_no_handoff_authority=True,
            correlation_id="correlation.connector-upgrade-evidence-receipt-blocked",
        )
    audit_readiness_source.replace((audit_evidence,))
    readiness_with_audit = await service.assess_handoff_readiness(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        correlation_id="correlation.connector-upgrade-handoff-readiness-with-audit",
    )
    assert readiness_with_audit.audit_readiness_evidence_id == audit_evidence.evidence_id
    assert readiness_with_audit.audit_readiness_evidence_digest == audit_evidence.canonical_digest
    assert readiness_with_audit.audit_readiness_evidence_current
    assert "connector.upgrade.handoff.audit-readiness-evidence-current" in (
        readiness_with_audit.satisfied_check_ids
    )
    assert readiness_with_audit.blocker_ids == (
        "connector.upgrade.handoff.blocked.itsm-change-missing",
        "connector.upgrade.handoff.blocked.maintenance-window-missing",
    )
    with pytest.raises(ConnectorUpgradeApprovalError, match="draft_not_current"):
        await service.get_latest_change_context_draft(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            correlation_id="correlation.connector-upgrade-change-context-evidence-drift",
        )
    audit_readiness_source.replace((replace(audit_evidence, canonical_digest="0" * 64),))
    with pytest.raises(ConnectorUpgradeApprovalError, match="integrity_invalid"):
        await service.assess_handoff_readiness(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            correlation_id="correlation.connector-upgrade-audit-evidence-integrity",
        )
    audit_readiness_source.replace((audit_evidence,))
    itsm_change_evidence_source.replace((itsm_evidence,))
    readiness_with_itsm = await service.assess_handoff_readiness(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        correlation_id="correlation.connector-upgrade-handoff-readiness-with-itsm",
    )
    assert readiness_with_itsm.itsm_change_evidence_id == itsm_evidence.evidence_id
    assert readiness_with_itsm.itsm_change_evidence_digest == itsm_evidence.canonical_digest
    assert readiness_with_itsm.itsm_change_evidence_current
    assert "connector.upgrade.handoff.itsm-change-current" in (
        readiness_with_itsm.satisfied_check_ids
    )
    assert readiness_with_itsm.blocker_ids == (
        "connector.upgrade.handoff.blocked.maintenance-window-missing",
    )
    assert readiness_with_itsm.evidence_valid_until == itsm_evidence.valid_until
    maintenance_window_evidence_source.replace((window_evidence,))
    complete_readiness = await service.assess_handoff_readiness(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        correlation_id="correlation.connector-upgrade-handoff-readiness-with-window",
    )
    assert complete_readiness.assessment_state == "evidence_complete"
    assert complete_readiness.maintenance_window_evidence_id == window_evidence.evidence_id
    assert complete_readiness.maintenance_window_evidence_current
    assert complete_readiness.blocker_ids == ()
    assert complete_readiness.evidence_valid_until == window_evidence.valid_until
    assert not complete_readiness.handoff_ready
    assert not complete_readiness.handoff_artifact_issued
    assert not complete_readiness.execution_authorized
    receipt = await service.create_evidence_receipt(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_readiness_digest=complete_readiness.canonical_digest,
        acknowledged_receipt_is_non_executable_and_grants_no_handoff_authority=True,
        correlation_id="correlation.connector-upgrade-evidence-receipt",
    )
    replayed_receipt = await service.create_evidence_receipt(
        actor=verifier,
        record_id=instance.record_id,
        request_id=request.request_id,
        expected_readiness_digest=complete_readiness.canonical_digest,
        acknowledged_receipt_is_non_executable_and_grants_no_handoff_authority=True,
        correlation_id="correlation.connector-upgrade-evidence-receipt-replay",
    )
    assert receipt == replayed_receipt
    assert receipt.assessment_digest == complete_readiness.canonical_digest
    assert receipt.required_check_ids == receipt.satisfied_check_ids
    assert receipt.evidence_receipt_only and not receipt.runtime_acceptable
    assert not receipt.approval_consumed and not receipt.handoff_artifact_issued
    assert not receipt.execution_authorized and not receipt.infrastructure_mutation_performed
    independent_auditor = instance_operator("subject.connector-upgrade-receipt-auditor")
    verification = await service.verify_evidence_receipt(
        actor=independent_auditor,
        record_id=instance.record_id,
        request_id=request.request_id,
        receipt=receipt,
        acknowledged_digest_integrity_is_not_authenticity_or_execution_authority=True,
        correlation_id="correlation.connector-upgrade-evidence-receipt-verify",
    )
    assert (
        verification.verification_state is ConnectorUpgradeEvidenceReceiptVerificationState.CURRENT
    )
    assert verification.integrity_valid and verification.current_state_matches
    assert verification.current_state_compared and not verification.receipt_expired
    assert not verification.authenticity_proven and not verification.execution_authorized
    assert not verification.handoff_ready and not verification.approval_consumed
    signed_receipt = await service.sign_evidence_receipt(
        actor=independent_auditor,
        record_id=instance.record_id,
        request_id=request.request_id,
        receipt=receipt,
        acknowledged_signature_authenticates_origin_but_grants_no_authority=True,
        correlation_id="correlation.connector-upgrade-signed-evidence-receipt",
    )
    authenticity_auditor = instance_operator("subject.connector-upgrade-authenticity-auditor")
    signed_verification = await service.verify_signed_evidence_receipt(
        actor=authenticity_auditor,
        record_id=instance.record_id,
        request_id=request.request_id,
        signed_receipt=signed_receipt,
        acknowledged_signature_is_not_approval_or_execution_authority=True,
        correlation_id="correlation.connector-upgrade-signed-evidence-verify",
    )
    assert (
        signed_verification.authenticity_state
        is ConnectorUpgradeEvidenceAuthenticityState.AUTHENTIC
    )
    assert signed_verification.authenticity_proven
    assert signed_verification.receipt_verification_state == "current"
    assert signed_verification.current_state_matches
    assert not signed_verification.execution_authorized
    assert not signed_verification.handoff_ready and not signed_verification.approval_consumed
    tampered_signature = replace(
        signed_receipt.signature,
        signature_value=(
            signed_receipt.signature.signature_value[:-1]
            + ("A" if signed_receipt.signature.signature_value[-1] != "A" else "B")
        ),
    )
    tampered_digest = ConnectorUpgradeApprovalService._digest(
        ConnectorUpgradeApprovalService._signed_evidence_envelope_payload(
            receipt, tampered_signature
        )
    )
    tampered_signed_receipt = replace(
        signed_receipt,
        signed_receipt_id=(f"connector-upgrade-signed-evidence-receipt.{tampered_digest[:24]}"),
        signature=tampered_signature,
        canonical_digest=tampered_digest,
    )
    invalid_signature = await service.verify_signed_evidence_receipt(
        actor=authenticity_auditor,
        record_id=instance.record_id,
        request_id=request.request_id,
        signed_receipt=tampered_signed_receipt,
        acknowledged_signature_is_not_approval_or_execution_authority=True,
        correlation_id="correlation.connector-upgrade-signed-evidence-invalid",
    )
    assert invalid_signature.authenticity_state is ConnectorUpgradeEvidenceAuthenticityState.INVALID
    assert not invalid_signature.authenticity_proven
    assert invalid_signature.receipt_verification_state == "not_compared"
    with pytest.raises(ConnectorUpgradeApprovalError, match="integrity_invalid"):
        await service.verify_evidence_receipt(
            actor=independent_auditor,
            record_id=instance.record_id,
            request_id=request.request_id,
            receipt=replace(receipt, plan_digest="0" * 64),
            acknowledged_digest_integrity_is_not_authenticity_or_execution_authority=True,
            correlation_id="correlation.connector-upgrade-evidence-receipt-tampered",
        )
    saved_time = current_time[0]
    current_time[0] = receipt.valid_until
    expired_verification = await service.verify_evidence_receipt(
        actor=independent_auditor,
        record_id=instance.record_id,
        request_id=request.request_id,
        receipt=receipt,
        acknowledged_digest_integrity_is_not_authenticity_or_execution_authority=True,
        correlation_id="correlation.connector-upgrade-evidence-receipt-expired",
    )
    assert (
        expired_verification.verification_state
        is ConnectorUpgradeEvidenceReceiptVerificationState.EXPIRED
    )
    assert expired_verification.receipt_expired
    assert not expired_verification.current_state_compared
    current_time[0] = saved_time
    with pytest.raises(ValueError, match="authority boundary"):
        replace(receipt, runtime_acceptable=True)
    with pytest.raises(ConnectorUpgradeApprovalError, match="readiness_not_current"):
        await service.create_evidence_receipt(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_readiness_digest="0" * 64,
            acknowledged_receipt_is_non_executable_and_grants_no_handoff_authority=True,
            correlation_id="correlation.connector-upgrade-evidence-receipt-stale",
        )
    maintenance_window_evidence_source.replace(
        (replace(window_evidence, canonical_digest="0" * 64),)
    )
    unverifiable = await service.verify_evidence_receipt(
        actor=independent_auditor,
        record_id=instance.record_id,
        request_id=request.request_id,
        receipt=receipt,
        acknowledged_digest_integrity_is_not_authenticity_or_execution_authority=True,
        correlation_id="correlation.connector-upgrade-evidence-receipt-unverifiable",
    )
    assert (
        unverifiable.verification_state
        is ConnectorUpgradeEvidenceReceiptVerificationState.UNVERIFIABLE
    )
    assert not unverifiable.current_state_compared
    with pytest.raises(ConnectorUpgradeApprovalError, match="window_evidence_integrity"):
        await service.assess_handoff_readiness(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            correlation_id="correlation.connector-upgrade-window-evidence-integrity",
        )
    maintenance_window_evidence_source.replace((window_evidence,))
    maintenance_window_evidence_source.replace(())
    stale_verification = await service.verify_evidence_receipt(
        actor=independent_auditor,
        record_id=instance.record_id,
        request_id=request.request_id,
        receipt=receipt,
        acknowledged_digest_integrity_is_not_authenticity_or_execution_authority=True,
        correlation_id="correlation.connector-upgrade-evidence-receipt-stale-evidence",
    )
    assert (
        stale_verification.verification_state
        is ConnectorUpgradeEvidenceReceiptVerificationState.STALE
    )
    assert stale_verification.current_state_compared
    assert not stale_verification.current_state_matches
    maintenance_window_evidence_source.replace((window_evidence,))
    itsm_change_evidence_source.replace((replace(itsm_evidence, canonical_digest="0" * 64),))
    with pytest.raises(ConnectorUpgradeApprovalError, match="itsm_change_evidence_integrity"):
        await service.assess_handoff_readiness(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            correlation_id="correlation.connector-upgrade-itsm-evidence-integrity",
        )
    itsm_change_evidence_source.replace((itsm_evidence,))
    with pytest.raises(ValueError, match="authority boundary"):
        replace(
            readiness,
            not_applicable_check_ids=(readiness.required_check_ids[0],),
        )
    assert not readiness.handoff_ready and not readiness.handoff_artifact_issued
    assert not readiness.approval_consumed and not readiness.target_contacted
    assert not readiness.package_rebound and not readiness.configuration_changed
    assert not readiness.execution_authorized
    assert not readiness.infrastructure_mutation_performed
    assert draft.state == "draft" and replayed_draft.reused
    assert latest_draft.draft_id == draft.draft_id
    assert draft.readiness_digest == readiness.canonical_digest
    assert not draft.itsm_dispatched and not draft.window_approved
    assert not draft.handoff_ready and not draft.handoff_artifact_issued
    assert not draft.approval_consumed and not draft.execution_authorized
    assert not draft.target_contacted and not draft.package_rebound
    assert not draft.configuration_changed
    assert not draft.infrastructure_mutation_performed
    current_time[0] = draft.valid_until
    with pytest.raises(ConnectorUpgradeApprovalError, match="draft_not_current"):
        await service.get_latest_change_context_draft(
            actor=verifier,
            record_id=instance.record_id,
            request_id=request.request_id,
            correlation_id="correlation.connector-upgrade-change-context-expired",
        )
    restored_draft = PostgreSQLConnectorUpgradeApprovalRepository._change_context_to_domain(
        cast(dict[str, object], ConnectorUpgradeApprovalService._normalize(asdict(draft)))
    )
    assert restored_draft == draft
    restored = PostgreSQLConnectorUpgradeApprovalRepository._revalidation_to_domain(
        cast(
            dict[str, object],
            ConnectorUpgradeApprovalService._normalize(asdict(revalidation)),
        )
    )
    assert restored == revalidation
    assert [item.result_code for item in audit.records].count(
        "connector_upgrade_approval_revalidated"
    ) == 1
    assert [item.result_code for item in audit.records].count(
        "connector_upgrade_change_context_draft_created"
    ) == 1
    assert [item.result_code for item in audit.records].count(
        "connector_upgrade_change_context_draft_reused"
    ) == 1


def test_upgrade_approval_revalidation_api_is_no_store_and_hides_custody_metadata(
    tmp_path: Path,
) -> None:
    (
        approval_service,
        upgrade_service,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        sources,
        _,
    ) = asyncio.run(approval_fixture())
    instance, candidate_receipt = sources
    requester = instance_operator()
    approver = instance_operator("subject.connector-upgrade-independent-approver")
    verifier = instance_operator("subject.connector-upgrade-independent-verifier")
    plan = asyncio.run(
        upgrade_service.plan(
            actor=requester,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            correlation_id="correlation.connector-upgrade-revalidation-api-plan",
        )
    )
    request = asyncio.run(
        approval_service.create(
            actor=requester,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            source_plan_digest=plan.canonical_digest,
            purpose="Submit this exact connector upgrade plan for independent human review.",
            acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-revalidation-api-request",
            correlation_id="correlation.connector-upgrade-revalidation-api-request",
        )
    )
    approval = asyncio.run(
        approval_service.decide(
            actor=approver,
            record_id=instance.record_id,
            request_id=request.request_id,
            expected_request_version=request.version,
            expected_request_digest=request.canonical_digest,
            outcome=ConnectorUpgradeApprovalOutcome.APPROVE,
            rationale="Approve the exact immutable plan after independent evidence review.",
            acknowledged_decision_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-revalidation-api-decision",
            correlation_id="correlation.connector-upgrade-revalidation-api-decision",
        )
    )
    assert approval.decision is not None
    app = create_app(
        settings(
            development_subject_id=verifier.subject_id,
            mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
        ),
        identity_provider=BasicTestIdentityProvider(verifier),
        registry_publication_service=publication_service,
        package_registration_service=registration_service,
        package_installation_service=package_service,
        connector_instance_creation_service=instance_service,
        connector_upgrade_approval_service=approval_service,
    )
    with TestClient(app) as client:
        app.state.connector_upgrade_readiness_service = upgrade_service
        login_response = login(client)
        trust_response = client.get(
            "/api/v1/connectors/instances/upgrade-evidence-signing-key-trust"
        )
        response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/revalidations",
            headers={
                "Idempotency-Key": "connector-upgrade-revalidation-api",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
            json={
                "schema_version": "atlas.connector-upgrade-approval-revalidation-input.v1",
                "expected_request_digest": request.canonical_digest,
                "expected_decision_digest": approval.decision.canonical_digest,
                "purpose": "Revalidate the exact approved plan without granting handoff authority.",
                "acknowledged_revalidation_grants_no_handoff_or_execution_authority": True,
            },
        )
        read_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/revalidations/latest"
        )
        readiness_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/handoff-readiness"
        )
        readiness_payload = readiness_response.json()["data"]
        readiness_digest = readiness_payload["canonical_digest"]
        receipt_without_csrf = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/evidence-receipts",
            json={
                "schema_version": "atlas.connector-upgrade-evidence-receipt-input.v1",
                "expected_readiness_digest": readiness_digest,
                "acknowledged_receipt_is_non_executable_and_grants_no_handoff_authority": True,
            },
        )
        blocked_receipt_response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/evidence-receipts",
            headers={"X-CSRF-Token": login_response.headers["X-CSRF-Token"]},
            json={
                "schema_version": "atlas.connector-upgrade-evidence-receipt-input.v1",
                "expected_readiness_digest": readiness_digest,
                "acknowledged_receipt_is_non_executable_and_grants_no_handoff_authority": True,
            },
        )
        uploaded_receipt = {
            "receipt_id": "connector-upgrade-evidence-receipt.uploaded",
            "schema_version": "atlas.connector-upgrade-evidence-receipt.v1",
            "version": 1,
            "assessment_id": readiness_payload["assessment_id"],
            "assessment_digest": readiness_payload["canonical_digest"],
            "request_id": request.request_id,
            "request_digest": request.canonical_digest,
            "decision_id": approval.decision.decision_id,
            "decision_digest": approval.decision.canonical_digest,
            "revalidation_id": readiness_payload["revalidation_id"],
            "revalidation_digest": readiness_payload["revalidation_digest"],
            "plan_id": plan.plan_id,
            "plan_digest": plan.canonical_digest,
            "organization_id": request.organization_id,
            "environment_id": request.environment_id,
            "created_by": verifier.subject_id,
            "audit_readiness_evidence_id": "connector-upgrade-audit-evidence.uploaded",
            "audit_readiness_evidence_digest": "a" * 64,
            "itsm_change_evidence_id": "connector-upgrade-itsm-evidence.uploaded",
            "itsm_change_evidence_digest": "b" * 64,
            "maintenance_window_evidence_id": "connector-upgrade-window-evidence.uploaded",
            "maintenance_window_evidence_digest": "c" * 64,
            "required_check_ids": readiness_payload["required_check_ids"],
            "satisfied_check_ids": readiness_payload["required_check_ids"],
            "not_applicable_check_ids": readiness_payload["not_applicable_check_ids"],
            "created_at": response.json()["data"]["revalidated_at"],
            "valid_until": response.json()["data"]["valid_until"],
            "canonical_digest": "d" * 64,
            "evidence_receipt_only": True,
            "runtime_acceptable": False,
            "approval_consumed": False,
            "handoff_ready": False,
            "handoff_artifact_issued": False,
            "target_contacted": False,
            "package_rebound": False,
            "configuration_changed": False,
            "execution_authorized": False,
            "infrastructure_mutation_performed": False,
        }
        verify_without_csrf = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/evidence-receipts/verify",
            json={
                "schema_version": (
                    "atlas.connector-upgrade-evidence-receipt-verification-input.v1"
                ),
                "receipt": uploaded_receipt,
                ("acknowledged_digest_integrity_is_not_authenticity_or_execution_authority"): True,
            },
        )
        authority_bearing_receipt = {**uploaded_receipt, "runtime_acceptable": True}
        verify_authority_response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/evidence-receipts/verify",
            headers={"X-CSRF-Token": login_response.headers["X-CSRF-Token"]},
            json={
                "schema_version": (
                    "atlas.connector-upgrade-evidence-receipt-verification-input.v1"
                ),
                "receipt": authority_bearing_receipt,
                ("acknowledged_digest_integrity_is_not_authenticity_or_execution_authority"): True,
            },
        )
        uploaded_signed_receipt = {
            "signed_receipt_id": "connector-upgrade-signed-evidence-receipt.uploaded",
            "schema_version": "atlas.connector-upgrade-signed-evidence-receipt.v1",
            "version": 1,
            "receipt": uploaded_receipt,
            "signature": {
                "key_id": "key.connector-upgrade-evidence.test",
                "key_version": "version.1",
                "signer_profile_id": "signer-profile.nonproduction-hmac",
                "signer_workload_id": "workload.connector-upgrade-evidence-signer",
                "algorithm": "algorithm.hmac-sha256-nonproduction",
                "signed_payload_digest": "e" * 64,
                "signature_value": "A" * 43,
                "signature_digest": "f" * 64,
                "issued_at": response.json()["data"]["revalidated_at"],
                "expires_at": response.json()["data"]["valid_until"],
            },
            "organization_id": request.organization_id,
            "environment_id": request.environment_id,
            "request_id": request.request_id,
            "canonical_digest": "1" * 64,
            "evidence_receipt_only": True,
            "authenticity_claimed": True,
            "runtime_acceptable": False,
            "approval_consumed": False,
            "handoff_ready": False,
            "handoff_artifact_issued": False,
            "target_contacted": False,
            "package_rebound": False,
            "configuration_changed": False,
            "execution_authorized": False,
            "infrastructure_mutation_performed": False,
        }
        signed_verify_without_csrf = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/signed-evidence-receipts/verify",
            json={
                "schema_version": (
                    "atlas.connector-upgrade-signed-evidence-receipt-verification-input.v1"
                ),
                "signed_receipt": uploaded_signed_receipt,
                "acknowledged_signature_is_not_approval_or_execution_authority": True,
            },
        )
        signed_authority_response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/signed-evidence-receipts/verify",
            headers={"X-CSRF-Token": login_response.headers["X-CSRF-Token"]},
            json={
                "schema_version": (
                    "atlas.connector-upgrade-signed-evidence-receipt-verification-input.v1"
                ),
                "signed_receipt": {
                    **uploaded_signed_receipt,
                    "execution_authorized": True,
                },
                "acknowledged_signature_is_not_approval_or_execution_authority": True,
            },
        )
        draft_response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/change-context-drafts",
            headers={
                "Idempotency-Key": "connector-upgrade-change-context-api",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
            json={
                "schema_version": "atlas.connector-upgrade-change-context-draft-input.v1",
                "expected_readiness_digest": readiness_digest,
                "proposed_window_start": (plan.generated_at + timedelta(hours=3)).isoformat(),
                "proposed_window_end": (plan.generated_at + timedelta(hours=4)).isoformat(),
                "justification": "Prepare the exact connector upgrade for governed ITSM review.",
                (
                    "acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority"
                ): True,
            },
        )
        draft_read_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request.request_id}/change-context-drafts/latest"
        )

    assert trust_response.status_code == 200, trust_response.text
    assert trust_response.headers["Cache-Control"] == "no-store"
    trust_data = trust_response.json()["data"]
    assert trust_data["provider_class"] == "provider.nonproduction-hmac"
    assert trust_data["provider_state"] == "available"
    assert trust_data["production_approved"] is False
    assert trust_data["keys"][0]["effective_state"] == "active"
    assert trust_data["keys"][0]["signing_eligible"] is True
    assert trust_data["keys"][0]["verification_trusted"] is True
    trust_rendered = trust_response.text.lower()
    for hidden in ("private_key", "key_material", "secret", "credential", "token", "endpoint"):
        assert hidden not in trust_rendered
    assert response.status_code == 201, response.text
    assert read_response.status_code == 200, read_response.text
    assert readiness_response.status_code == 200, readiness_response.text
    assert receipt_without_csrf.status_code == 403, receipt_without_csrf.text
    assert blocked_receipt_response.status_code == 409, blocked_receipt_response.text
    assert blocked_receipt_response.json()["code"].endswith("readiness_not_current")
    assert verify_without_csrf.status_code == 403, verify_without_csrf.text
    assert verify_authority_response.status_code == 422, verify_authority_response.text
    assert signed_verify_without_csrf.status_code == 403, signed_verify_without_csrf.text
    assert signed_authority_response.status_code == 422, signed_authority_response.text
    assert draft_response.status_code == 201, draft_response.text
    assert draft_read_response.status_code == 200, draft_read_response.text
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["governance_ready"] is True and data["handoff_ready"] is False
    assert data["execution_authorized"] is False
    readiness_data = readiness_response.json()["data"]
    assert readiness_data["schema_version"] == "atlas.connector-upgrade-handoff-readiness.v5"
    assert readiness_data["assessment_state"] == "blocked"
    assert readiness_data["handoff_ready"] is False
    assert readiness_data["handoff_artifact_issued"] is False
    assert readiness_data["approval_consumed"] is False
    assert len(readiness_data["required_check_ids"]) == 9
    assert len(readiness_data["not_applicable_check_ids"]) == 3
    assert len(readiness_data["blocker_ids"]) == 3
    assert readiness_data["applicability_policy_digest"]
    assert readiness_data["audit_readiness_evidence_id"] is None
    assert readiness_data["audit_readiness_evidence_digest"] is None
    assert readiness_data["audit_readiness_evidence_current"] is False
    assert readiness_data["itsm_change_evidence_id"] is None
    assert readiness_data["itsm_change_evidence_digest"] is None
    assert readiness_data["itsm_change_evidence_current"] is False
    assert readiness_data["maintenance_window_evidence_id"] is None
    assert readiness_data["maintenance_window_evidence_digest"] is None
    assert readiness_data["maintenance_window_evidence_current"] is False
    draft_data = draft_response.json()["data"]
    assert draft_data["state"] == "draft"
    assert draft_data["readiness_digest"] == readiness_data["canonical_digest"]
    assert draft_data["itsm_dispatched"] is False
    assert draft_data["window_approved"] is False
    assert draft_data["handoff_ready"] is False
    assert draft_data["target_contacted"] is False
    assert draft_data["package_rebound"] is False
    assert draft_data["configuration_changed"] is False
    assert draft_data["execution_authorized"] is False
    assert draft_read_response.json()["data"]["draft_id"] == draft_data["draft_id"]
    assert draft_response.headers["Cache-Control"] == "no-store"
    rendered = f"{response.text} {draft_response.text} {draft_read_response.text}".lower()
    for hidden in (
        "revalidation_fingerprint",
        "idempotency_key",
        "credential",
        "target_endpoint",
        "request_fingerprint",
        "ledger_id",
        "ledger_generation",
        "integrity_verification_digest",
        "redaction_policy_digest",
        "retention_policy_digest",
    ):
        assert hidden not in rendered
