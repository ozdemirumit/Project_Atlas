from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.itsm.adapters.memory import InMemoryItsmIntegrationProfileRepository
from atlas.modules.itsm.adapters.onboarding import (
    DeterministicDevelopmentItsmSandboxOnboardingEvidenceSource,
    InMemoryItsmSandboxOnboardingPolicyProvenanceSource,
    InMemoryItsmSandboxOnboardingPolicySource,
    InMemoryItsmSandboxOnboardingPolicyTrustSource,
    build_development_itsm_sandbox_onboarding_policy,
    build_development_itsm_sandbox_onboarding_policy_authenticity,
)
from atlas.modules.itsm.adapters.postgres import PostgreSQLItsmIntegrationProfileRepository
from atlas.modules.itsm.adapters.sandbox import (
    DeterministicNoNetworkItsmSandboxConformanceAdapter,
)
from atlas.modules.itsm.application.service import ItsmIntegrationError, ItsmIntegrationService
from atlas.modules.itsm.domain.models import (
    ITSM_SANDBOX_ONBOARDING_REQUIREMENTS,
    ItsmAllowedOperation,
    ItsmFieldMapping,
    ItsmProfileLifecycle,
    ItsmProviderFamily,
    ItsmReadinessState,
    ItsmSandboxConformanceState,
    ItsmSandboxOnboardingAdapterRule,
    ItsmSandboxOnboardingPolicy,
    ItsmSandboxOnboardingPolicyProvenance,
    ItsmSandboxOnboardingPolicyTrustKey,
    ItsmSandboxOnboardingPolicyTrustKeyState,
    ItsmSandboxOnboardingState,
    ItsmWriteSemantics,
)

NOW = datetime(2026, 8, 13, 4, 0, tzinfo=UTC)


class ProductionEligibleSandboxAdapter(DeterministicNoNetworkItsmSandboxConformanceAdapter):
    async def assess(self, **values: object):  # type: ignore[no-untyped-def]
        diagnostic = await super().assess(**values)  # type: ignore[arg-type]
        return replace(diagnostic, production_eligible=True)


class ApprovedSandboxOnboardingEvidenceSource(
    DeterministicDevelopmentItsmSandboxOnboardingEvidenceSource
):
    async def get(self, **values: object):  # type: ignore[no-untyped-def]
        evidence = await super().get(**values)  # type: ignore[arg-type]
        assert evidence is not None
        evidence = replace(
            evidence,
            adapter_sandbox_approved=True,
            security_approval_reference="approval.security.itsm-sandbox",
            deployment_approval_reference="approval.deployment.itsm-sandbox",
            production_eligible=True,
            canonical_digest="0" * 64,
        )
        return replace(
            evidence,
            canonical_digest=ItsmIntegrationService._digest(
                ItsmIntegrationService._onboarding_evidence_payload(evidence)
            ),
        )


class MismatchedSandboxOnboardingEvidenceSource(
    DeterministicDevelopmentItsmSandboxOnboardingEvidenceSource
):
    async def get(self, **values: object):  # type: ignore[no-untyped-def]
        evidence = await super().get(**values)  # type: ignore[arg-type]
        assert evidence is not None
        evidence = replace(evidence, profile_digest="f" * 64, canonical_digest="0" * 64)
        return replace(
            evidence,
            canonical_digest=ItsmIntegrationService._digest(
                ItsmIntegrationService._onboarding_evidence_payload(evidence)
            ),
        )


class FailingSandboxOnboardingEvidenceSource:
    async def get(self, **values: object):  # type: ignore[no-untyped-def]
        del values
        raise RuntimeError("provider-native failure must remain contained")


class FailingSandboxOnboardingPolicySource:
    async def list_scope(self, **values: object):  # type: ignore[no-untyped-def]
        del values
        raise RuntimeError("policy authority failure must remain contained")


class FailingSandboxOnboardingPolicyProvenanceSource:
    async def list_scope(self, **values: object):  # type: ignore[no-untyped-def]
        del values
        raise RuntimeError("provenance authority failure must remain contained")


class FailingSandboxOnboardingPolicyTrustSource:
    async def list_scope(self, **values: object):  # type: ignore[no-untyped-def]
        del values
        raise RuntimeError("trust authority failure must remain contained")


class FailingSandboxOnboardingPolicyVerifier:
    @property
    def supported_algorithms(self) -> tuple[str, ...]:
        return ("algorithm.hmac-sha256-nonproduction",)

    async def verify(self, **values: object) -> bool:
        del values
        raise RuntimeError("verification boundary failure must remain contained")


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def actor() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.itsm.integration-admin",
        display_name="ITSM Integration Admin",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.test",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.development",
        role_ids=("role.itsm-integration-admin",),
    )


def policy_source() -> InMemoryItsmSandboxOnboardingPolicySource:
    return InMemoryItsmSandboxOnboardingPolicySource(
        (
            build_development_itsm_sandbox_onboarding_policy(
                organization_id="organization.development",
                environment_id="environment.test",
                site_id="site.local",
                now=NOW,
            ),
        )
    )


def policy(**overrides: Any) -> ItsmSandboxOnboardingPolicy:
    baseline = build_development_itsm_sandbox_onboarding_policy(
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        now=NOW,
    )
    candidate = replace(baseline, canonical_digest="0" * 64, **overrides)
    return replace(
        candidate,
        canonical_digest=ItsmIntegrationService._digest(
            ItsmIntegrationService._onboarding_policy_payload(candidate)
        ),
    )


def authenticity_kwargs(
    *policies: ItsmSandboxOnboardingPolicy,
) -> dict[str, Any]:
    snapshots = policies or (policy(),)
    provenances = []
    trust_keys = {}
    verifier = None
    for snapshot in snapshots:
        provenance, trust_key, verifier = (
            build_development_itsm_sandbox_onboarding_policy_authenticity(snapshot)
        )
        provenances.append(provenance)
        trust_keys[trust_key.canonical_digest] = trust_key
    assert verifier is not None
    return {
        "sandbox_onboarding_policy_provenance_source": (
            InMemoryItsmSandboxOnboardingPolicyProvenanceSource(tuple(provenances))
        ),
        "sandbox_onboarding_policy_trust_source": InMemoryItsmSandboxOnboardingPolicyTrustSource(
            tuple(trust_keys.values())
        ),
        "sandbox_onboarding_policy_verifier": verifier,
    }


def provenance(**overrides: Any) -> ItsmSandboxOnboardingPolicyProvenance:
    baseline, _, _ = build_development_itsm_sandbox_onboarding_policy_authenticity(policy())
    candidate = replace(baseline, canonical_digest="0" * 64, **overrides)
    candidate = replace(
        candidate,
        signed_payload_digest=ItsmIntegrationService._digest(
            ItsmIntegrationService._onboarding_policy_provenance_signed_payload(candidate)
        ),
        signature_digest=ItsmIntegrationService._digest(candidate.signature_value),
    )
    return replace(
        candidate,
        canonical_digest=ItsmIntegrationService._digest(
            ItsmIntegrationService._onboarding_policy_provenance_payload(candidate)
        ),
    )


def trust_key(**overrides: Any) -> ItsmSandboxOnboardingPolicyTrustKey:
    _, baseline, _ = build_development_itsm_sandbox_onboarding_policy_authenticity(policy())
    candidate = replace(baseline, canonical_digest="0" * 64, **overrides)
    return replace(
        candidate,
        canonical_digest=ItsmIntegrationService._digest(
            ItsmIntegrationService._onboarding_policy_trust_payload(candidate)
        ),
    )


def custom_authenticity_kwargs(
    *,
    provenances: tuple[ItsmSandboxOnboardingPolicyProvenance, ...] | None = None,
    trust_keys: tuple[ItsmSandboxOnboardingPolicyTrustKey, ...] | None = None,
    provenance_source: object | None = None,
    trust_source: object | None = None,
    verifier: object | None = None,
) -> dict[str, Any]:
    default_provenance, default_trust, default_verifier = (
        build_development_itsm_sandbox_onboarding_policy_authenticity(policy())
    )
    return {
        "sandbox_onboarding_policy_provenance_source": (
            provenance_source
            if provenance_source is not None
            else InMemoryItsmSandboxOnboardingPolicyProvenanceSource(
                provenances if provenances is not None else (default_provenance,)
            )
        ),
        "sandbox_onboarding_policy_trust_source": (
            trust_source
            if trust_source is not None
            else InMemoryItsmSandboxOnboardingPolicyTrustSource(
                trust_keys if trust_keys is not None else (default_trust,)
            )
        ),
        "sandbox_onboarding_policy_verifier": verifier or default_verifier,
    }


def without_verifier_kwargs() -> dict[str, Any]:
    values = custom_authenticity_kwargs()
    values["sandbox_onboarding_policy_verifier"] = None
    return values


def mappings() -> tuple[ItsmFieldMapping, ...]:
    return (
        ItsmFieldMapping("work_notes", "work_notes", ItsmWriteSemantics.APPEND_ONLY),
        ItsmFieldMapping(
            "u_atlas_report_reference",
            "u_atlas_report_reference",
            ItsmWriteSemantics.REFERENCE_ONLY,
        ),
        ItsmFieldMapping(
            "u_atlas_review_state",
            "u_atlas_review_state",
            ItsmWriteSemantics.REFERENCE_ONLY,
        ),
    )


def create_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "profile_key": "itsm.sandbox.primary",
        "display_name": "Primary ITSM sandbox",
        "provider_family": ItsmProviderFamily.GENERIC_REST,
        "instance_reference": "itsm-instance.sandbox.primary",
        "owner_id": "team.service-management",
        "purpose": "Validate governed report handoff mappings in an isolated ITSM sandbox.",
        "endpoint_origin": "https://itsm-sandbox.example.invalid",
        "trust_boundary_reference": "trust-boundary.itsm.sandbox",
        "secret_reference_id": "secret.itsm.sandbox.writer",
        "classification_ceiling": DataClassification.INTERNAL,
        "allowed_operations": (ItsmAllowedOperation.APPEND_ANALYSIS,),
        "mapping_version": 1,
        "field_mappings": mappings(),
        "sandbox_validation_reference": None,
        "sandbox_validation_digest": None,
        "audit_profile_id": "audit-profile.itsm.sandbox",
        "acknowledged_configuration_only": True,
        "idempotency_key": "itsm-profile-create-0001",
        "correlation_id": "correlation.itsm.profile.create",
    }
    values.update(overrides)
    return values


@pytest.mark.asyncio
async def test_profile_readiness_is_deterministic_and_never_authorizes_dispatch() -> None:
    sink = CollectingAuditSink()
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=sink,
        environment_id="environment.test",
        clock=lambda: NOW,
    )

    blocked = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    replay = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]

    assert blocked.readiness.state is ItsmReadinessState.BLOCKED
    assert replay.profile_id == blocked.profile_id
    assert replay.reused is True
    assert not any(
        (
            blocked.readiness.dispatch_authorized,
            blocked.readiness.external_record_mutation_authorized,
            blocked.readiness.workflow_approved,
            blocked.readiness.execution_authorized,
        )
    )
    assert {item.reason_code for item in blocked.readiness.checks} >= {
        "itsm.readiness.sandbox_validation_missing"
    }


@pytest.mark.asyncio
async def test_sandbox_evidence_makes_profile_ready_for_sandbox_only() -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    profile = await service.create(
        actor=actor(),
        **create_values(
            sandbox_validation_reference="validation.itsm.sandbox.001",
            sandbox_validation_digest="a" * 64,
        ),  # type: ignore[arg-type]
    )

    assert profile.readiness.state is ItsmReadinessState.READY_FOR_SANDBOX
    assert all(item.state.value == "satisfied" for item in profile.readiness.checks)
    assert profile.lifecycle is ItsmProfileLifecycle.ACTIVE


@pytest.mark.asyncio
async def test_retirement_is_optimistic_and_preserves_history() -> None:
    repository = InMemoryItsmIntegrationProfileRepository()
    service = ItsmIntegrationService(
        repository=repository,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    with pytest.raises(ItsmIntegrationError, match="version_conflict"):
        await service.retire(
            actor=actor(),
            profile_id=profile.profile_id,
            expected_version=9,
            reason="Retire the sandbox profile after replacing its governed mapping contract.",
            acknowledged_history_preserved_and_dispatch_absent=True,
            idempotency_key="itsm-profile-retire-stale",
            correlation_id="correlation.itsm.profile.retire.stale",
        )
    retired = await service.retire(
        actor=actor(),
        profile_id=profile.profile_id,
        expected_version=1,
        reason="Retire the sandbox profile after replacing its governed mapping contract.",
        acknowledged_history_preserved_and_dispatch_absent=True,
        idempotency_key="itsm-profile-retire-0001",
        correlation_id="correlation.itsm.profile.retire",
    )
    assert retired.lifecycle is ItsmProfileLifecycle.RETIRED
    assert retired.version == 2
    assert (await repository.get(profile_id=profile.profile_id)) == retired


def test_mapping_rejects_arbitrary_or_mutable_fields() -> None:
    with pytest.raises(ValueError, match="allowlist"):
        ItsmFieldMapping("password", "password", ItsmWriteSemantics.REFERENCE_ONLY)
    with pytest.raises(ValueError, match="append-only"):
        ItsmFieldMapping("work_notes", "work_notes", ItsmWriteSemantics.REFERENCE_ONLY)


@pytest.mark.asyncio
async def test_postgres_payload_round_trip_preserves_readiness_and_no_authority() -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    payload = ItsmIntegrationService._normalize(asdict(profile))
    assert isinstance(payload, dict)
    restored = PostgreSQLItsmIntegrationProfileRepository._to_domain(payload)

    assert restored == profile
    assert restored.readiness.canonical_digest == profile.readiness.canonical_digest
    assert restored.secret_reference_id == "secret.itsm.sandbox.writer"
    assert restored.readiness.dispatch_authorized is False
    assert restored.readiness.external_record_mutation_authorized is False


@pytest.mark.asyncio
async def test_sandbox_conformance_is_exact_profile_bound_idempotent_and_diagnostic_only() -> None:
    repository = InMemoryItsmIntegrationProfileRepository()
    service = ItsmIntegrationService(
        repository=repository,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_conformance_adapter=DeterministicNoNetworkItsmSandboxConformanceAdapter(),
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    values = {
        "actor": actor(),
        "profile_id": profile.profile_id,
        "expected_profile_version": profile.version,
        "acknowledged_diagnostic_only_and_no_dispatch": True,
        "idempotency_key": "itsm-sandbox-assessment-0001",
        "correlation_id": "correlation.itsm.sandbox.assessment",
    }

    assessment = await service.assess_sandbox_conformance(**values)  # type: ignore[arg-type]
    replay = await service.assess_sandbox_conformance(**values)  # type: ignore[arg-type]
    latest = await service.latest_sandbox_conformance(
        actor=actor(),
        profile_id=profile.profile_id,
        correlation_id="correlation.itsm.sandbox.latest",
    )

    assert assessment.state is ItsmSandboxConformanceState.CONFORMANT
    assert assessment.profile_digest == profile.canonical_digest
    assert assessment.mapping_version == profile.mapping_version
    assert assessment.adapter_id == "adapter.itsm.synthetic-no-network"
    assert replay.assessment_id == assessment.assessment_id
    assert replay.reused is True
    assert latest == assessment
    assert assessment.sandbox_conformant is True
    assert not any(
        (
            assessment.production_ready,
            assessment.dispatch_authorized,
            assessment.external_record_mutation_authorized,
            assessment.workflow_approved,
            assessment.execution_authorized,
            assessment.infrastructure_mutation_performed,
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "adapter_state",
    [
        ItsmSandboxConformanceState.UNAVAILABLE,
        ItsmSandboxConformanceState.TRUST_FAILED,
        ItsmSandboxConformanceState.CREDENTIAL_FAILED,
        ItsmSandboxConformanceState.PERMISSION_FAILED,
        ItsmSandboxConformanceState.MAPPING_FAILED,
        ItsmSandboxConformanceState.ROUND_TRIP_FAILED,
    ],
)
async def test_sandbox_adapter_outcomes_remain_bounded(
    adapter_state: ItsmSandboxConformanceState,
) -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_conformance_adapter=DeterministicNoNetworkItsmSandboxConformanceAdapter(
            state=adapter_state
        ),
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    assessment = await service.assess_sandbox_conformance(
        actor=actor(),
        profile_id=profile.profile_id,
        expected_profile_version=profile.version,
        acknowledged_diagnostic_only_and_no_dispatch=True,
        idempotency_key=f"itsm-sandbox-{adapter_state.value}",
        correlation_id="correlation.itsm.sandbox.failure",
    )

    assert assessment.state is adapter_state
    assert assessment.sandbox_conformant is False
    assert assessment.reason_codes[0].startswith("itsm.sandbox-conformance.")


@pytest.mark.asyncio
async def test_sandbox_conformance_blocks_incomplete_profile_before_adapter() -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_conformance_adapter=DeterministicNoNetworkItsmSandboxConformanceAdapter(),
        clock=lambda: NOW,
    )
    profile = await service.create(
        actor=actor(),
        **create_values(field_mappings=(mappings()[0],)),  # type: ignore[arg-type]
    )
    assessment = await service.assess_sandbox_conformance(
        actor=actor(),
        profile_id=profile.profile_id,
        expected_profile_version=profile.version,
        acknowledged_diagnostic_only_and_no_dispatch=True,
        idempotency_key="itsm-sandbox-profile-blocked",
        correlation_id="correlation.itsm.sandbox.blocked",
    )

    assert assessment.state is ItsmSandboxConformanceState.PROFILE_BLOCKED
    assert assessment.adapter_id == "adapter.itsm.application"


@pytest.mark.asyncio
async def test_sandbox_assessment_postgres_payload_round_trip_preserves_boundaries() -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_conformance_adapter=DeterministicNoNetworkItsmSandboxConformanceAdapter(),
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    assessment = await service.assess_sandbox_conformance(
        actor=actor(),
        profile_id=profile.profile_id,
        expected_profile_version=profile.version,
        acknowledged_diagnostic_only_and_no_dispatch=True,
        idempotency_key="itsm-sandbox-postgres-roundtrip",
        correlation_id="correlation.itsm.sandbox.postgres",
    )
    payload = ItsmIntegrationService._normalize(asdict(assessment))
    assert isinstance(payload, dict)
    restored = PostgreSQLItsmIntegrationProfileRepository._sandbox_to_domain(payload)

    assert restored == assessment
    assert restored.profile_digest == profile.canonical_digest
    assert restored.dispatch_authorized is False


@pytest.mark.asyncio
async def test_sandbox_onboarding_readiness_blocks_synthetic_deployment_evidence() -> None:
    sink = CollectingAuditSink()
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=sink,
        environment_id="environment.test",
        sandbox_conformance_adapter=DeterministicNoNetworkItsmSandboxConformanceAdapter(),
        sandbox_onboarding_evidence_source=(
            DeterministicDevelopmentItsmSandboxOnboardingEvidenceSource()
        ),
        sandbox_onboarding_policy_source=policy_source(),
        **authenticity_kwargs(),
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    await service.assess_sandbox_conformance(
        actor=actor(),
        profile_id=profile.profile_id,
        expected_profile_version=profile.version,
        acknowledged_diagnostic_only_and_no_dispatch=True,
        idempotency_key="itsm-sandbox-onboarding-blocked",
        correlation_id="correlation.itsm.sandbox.onboarding.assess",
    )

    dossier = await service.sandbox_onboarding_readiness(
        actor=actor(),
        profile_id=profile.profile_id,
        correlation_id="correlation.itsm.sandbox.onboarding.read",
    )

    assert dossier.state is ItsmSandboxOnboardingState.BLOCKED
    assert len(dossier.requirements) == 12
    assert {item.reason_code for item in dossier.requirements if item.state.value == "blocked"} >= {
        "itsm.sandbox-onboarding.adapter_not_onboarding_eligible",
        "itsm.sandbox-onboarding.owner_approvals_missing",
    }
    assert not any(
        (
            dossier.sandbox_onboarding_ready,
            dossier.production_ready,
            dossier.dispatch_authorized,
            dossier.external_record_mutation_authorized,
            dossier.workflow_approved,
            dossier.execution_authorized,
            dossier.infrastructure_mutation_performed,
        )
    )
    assert sink.records[-1].result_code == "itsm_sandbox_onboarding_blocked"


@pytest.mark.asyncio
async def test_sandbox_onboarding_readiness_distinguishes_missing_conformance() -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_onboarding_evidence_source=(
            DeterministicDevelopmentItsmSandboxOnboardingEvidenceSource()
        ),
        sandbox_onboarding_policy_source=policy_source(),
        **authenticity_kwargs(),
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]

    dossier = await service.sandbox_onboarding_readiness(
        actor=actor(),
        profile_id=profile.profile_id,
        correlation_id="correlation.itsm.sandbox.onboarding.missing",
    )

    conformance = next(
        item
        for item in dossier.requirements
        if item.requirement_id == "itsm.sandbox-onboarding.conformance-current"
    )
    assert conformance.reason_code == "itsm.sandbox-onboarding.conformance_missing"


@pytest.mark.asyncio
async def test_sandbox_onboarding_readiness_requires_all_authoritative_evidence() -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_conformance_adapter=ProductionEligibleSandboxAdapter(),
        sandbox_onboarding_evidence_source=ApprovedSandboxOnboardingEvidenceSource(),
        sandbox_onboarding_policy_source=policy_source(),
        **authenticity_kwargs(),
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    assessment = await service.assess_sandbox_conformance(
        actor=actor(),
        profile_id=profile.profile_id,
        expected_profile_version=profile.version,
        acknowledged_diagnostic_only_and_no_dispatch=True,
        idempotency_key="itsm-sandbox-onboarding-ready",
        correlation_id="correlation.itsm.sandbox.onboarding.ready.assess",
    )

    dossier = await service.sandbox_onboarding_readiness(
        actor=actor(),
        profile_id=profile.profile_id,
        correlation_id="correlation.itsm.sandbox.onboarding.ready",
    )

    assert dossier.state is ItsmSandboxOnboardingState.READY
    assert dossier.sandbox_onboarding_ready is True
    assert dossier.conformance_assessment_id == assessment.assessment_id
    assert dossier.conformance_assessment_digest == assessment.canonical_digest
    assert dossier.policy_id == "policy.itsm-sandbox-onboarding.development"
    assert dossier.policy_version == 1
    assert dossier.policy_digest == policy().canonical_digest
    assert dossier.policy_issuer == "issuer.atlas-development"
    assert dossier.policy_expires_at == NOW + timedelta(days=30)
    assert dossier.policy_provenance_id == (
        "provenance.policy.itsm-sandbox-onboarding.development.1"
    )
    assert dossier.policy_signing_key_id == "signing-key.itsm-policy.development"
    assert dossier.policy_signing_key_version == "version.1"
    assert dossier.policy_signature_algorithm == "algorithm.hmac-sha256-nonproduction"
    assert dossier.policy_signed_at == NOW
    assert dossier.policy_verified_at == NOW
    assert all(item.state.value == "satisfied" for item in dossier.requirements)
    assert dossier.production_ready is False
    assert dossier.dispatch_authorized is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("evidence_source", "expected_reason"),
    [
        (
            MismatchedSandboxOnboardingEvidenceSource(),
            "itsm.sandbox-onboarding.evidence_binding_invalid",
        ),
        (
            FailingSandboxOnboardingEvidenceSource(),
            "itsm.sandbox-onboarding.evidence_source_unavailable",
        ),
    ],
)
async def test_sandbox_onboarding_readiness_contains_invalid_or_failed_evidence_sources(
    evidence_source: object,
    expected_reason: str,
) -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_conformance_adapter=DeterministicNoNetworkItsmSandboxConformanceAdapter(),
        sandbox_onboarding_evidence_source=evidence_source,  # type: ignore[arg-type]
        sandbox_onboarding_policy_source=policy_source(),
        **authenticity_kwargs(),
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    await service.assess_sandbox_conformance(
        actor=actor(),
        profile_id=profile.profile_id,
        expected_profile_version=profile.version,
        acknowledged_diagnostic_only_and_no_dispatch=True,
        idempotency_key=f"itsm-sandbox-onboarding-{expected_reason.rsplit('.', 1)[-1]}",
        correlation_id="correlation.itsm.sandbox.onboarding.evidence-failure",
    )

    dossier = await service.sandbox_onboarding_readiness(
        actor=actor(),
        profile_id=profile.profile_id,
        correlation_id="correlation.itsm.sandbox.onboarding.evidence-failure.read",
    )

    assert dossier.state is ItsmSandboxOnboardingState.BLOCKED
    assert {item.reason_code for item in dossier.requirements} >= {expected_reason}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "expected_error"),
    [
        (None, "itsm_sandbox_onboarding_policy_unavailable"),
        (
            InMemoryItsmSandboxOnboardingPolicySource(),
            "itsm_sandbox_onboarding_policy_unavailable",
        ),
        (
            FailingSandboxOnboardingPolicySource(),
            "itsm_sandbox_onboarding_policy_unavailable",
        ),
        (
            InMemoryItsmSandboxOnboardingPolicySource(
                (replace(policy(), canonical_digest="f" * 64),)
            ),
            "itsm_sandbox_onboarding_policy_integrity_failed",
        ),
        (
            InMemoryItsmSandboxOnboardingPolicySource(
                (policy(organization_id="organization.foreign"),)
            ),
            "itsm_sandbox_onboarding_policy_scope_invalid",
        ),
        (
            InMemoryItsmSandboxOnboardingPolicySource(
                (
                    policy(
                        requirement_ids=(
                            *ITSM_SANDBOX_ONBOARDING_REQUIREMENTS[:-1],
                            "itsm.sandbox-onboarding.unsupported",
                        )
                    ),
                )
            ),
            "itsm_sandbox_onboarding_policy_requirements_unsupported",
        ),
        (
            InMemoryItsmSandboxOnboardingPolicySource(
                (policy(effective_at=NOW + timedelta(hours=1)),)
            ),
            "itsm_sandbox_onboarding_policy_not_effective",
        ),
        (
            InMemoryItsmSandboxOnboardingPolicySource(
                (
                    policy(
                        issued_at=NOW - timedelta(hours=2),
                        effective_at=NOW - timedelta(hours=2),
                        expires_at=NOW - timedelta(hours=1),
                    ),
                )
            ),
            "itsm_sandbox_onboarding_policy_provenance_expired",
        ),
        (
            InMemoryItsmSandboxOnboardingPolicySource(
                (policy(), policy(policy_id="policy.itsm-sandbox-onboarding.secondary"))
            ),
            "itsm_sandbox_onboarding_policy_ambiguous",
        ),
    ],
)
async def test_sandbox_onboarding_policy_resolution_fails_closed(
    source: object,
    expected_error: str,
) -> None:
    source_policies = (
        source.policies
        if isinstance(source, InMemoryItsmSandboxOnboardingPolicySource) and source.policies
        else (policy(),)
    )
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_onboarding_policy_source=source,  # type: ignore[arg-type]
        **authenticity_kwargs(*source_policies),
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]

    with pytest.raises(ItsmIntegrationError, match=expected_error):
        await service.sandbox_onboarding_readiness(
            actor=actor(),
            profile_id=profile.profile_id,
            correlation_id="correlation.itsm.sandbox.onboarding.policy-failure",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("auth_kwargs", "expected_error"),
    [
        ({}, "itsm_sandbox_onboarding_policy_provenance_unavailable"),
        (
            custom_authenticity_kwargs(provenances=()),
            "itsm_sandbox_onboarding_policy_provenance_unavailable",
        ),
        (
            custom_authenticity_kwargs(
                provenance_source=FailingSandboxOnboardingPolicyProvenanceSource()
            ),
            "itsm_sandbox_onboarding_policy_provenance_unavailable",
        ),
        (
            custom_authenticity_kwargs(
                provenances=(
                    provenance(),
                    provenance(
                        provenance_id=(
                            "provenance.policy.itsm-sandbox-onboarding.development.secondary"
                        )
                    ),
                )
            ),
            "itsm_sandbox_onboarding_policy_provenance_ambiguous",
        ),
        (
            custom_authenticity_kwargs(
                provenances=(replace(provenance(), canonical_digest="f" * 64),)
            ),
            "itsm_sandbox_onboarding_policy_provenance_integrity_failed",
        ),
        (
            custom_authenticity_kwargs(
                provenances=(provenance(organization_id="organization.foreign"),)
            ),
            "itsm_sandbox_onboarding_policy_provenance_binding_invalid",
        ),
        (
            custom_authenticity_kwargs(
                provenances=(provenance(signed_at=NOW - timedelta(minutes=1)),)
            ),
            "itsm_sandbox_onboarding_policy_provenance_binding_invalid",
        ),
        (
            custom_authenticity_kwargs(
                provenances=(provenance(expires_at=NOW + timedelta(days=29)),)
            ),
            "itsm_sandbox_onboarding_policy_provenance_binding_invalid",
        ),
        (
            custom_authenticity_kwargs(
                provenances=(
                    provenance(
                        signed_at=NOW + timedelta(hours=1),
                        expires_at=NOW + timedelta(hours=2),
                    ),
                )
            ),
            "itsm_sandbox_onboarding_policy_provenance_not_effective",
        ),
        (
            custom_authenticity_kwargs(
                provenances=(
                    provenance(
                        signed_at=NOW - timedelta(hours=2),
                        expires_at=NOW - timedelta(hours=1),
                    ),
                )
            ),
            "itsm_sandbox_onboarding_policy_provenance_expired",
        ),
        (
            custom_authenticity_kwargs(
                provenances=(provenance(algorithm="algorithm.unsupported-signature"),)
            ),
            "itsm_sandbox_onboarding_policy_algorithm_unsupported",
        ),
        (
            custom_authenticity_kwargs(provenances=(provenance(signature_value="A" * 43),)),
            "itsm_sandbox_onboarding_policy_signature_invalid",
        ),
        (
            without_verifier_kwargs(),
            "itsm_sandbox_onboarding_policy_verifier_unavailable",
        ),
        (
            custom_authenticity_kwargs(verifier=FailingSandboxOnboardingPolicyVerifier()),
            "itsm_sandbox_onboarding_policy_verifier_unavailable",
        ),
    ],
)
async def test_sandbox_onboarding_policy_provenance_fails_closed(
    auth_kwargs: dict[str, Any],
    expected_error: str,
) -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_onboarding_policy_source=policy_source(),
        **auth_kwargs,
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]

    with pytest.raises(ItsmIntegrationError, match=expected_error):
        await service.sandbox_onboarding_readiness(
            actor=actor(),
            profile_id=profile.profile_id,
            correlation_id="correlation.itsm.sandbox.onboarding.provenance-failure",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("auth_kwargs", "expected_error"),
    [
        (
            custom_authenticity_kwargs(trust_keys=()),
            "itsm_sandbox_onboarding_policy_trust_unavailable",
        ),
        (
            custom_authenticity_kwargs(trust_source=FailingSandboxOnboardingPolicyTrustSource()),
            "itsm_sandbox_onboarding_policy_trust_unavailable",
        ),
        (
            custom_authenticity_kwargs(
                trust_keys=(
                    trust_key(),
                    trust_key(signing_key_id="signing-key.itsm-policy.secondary"),
                )
            ),
            "itsm_sandbox_onboarding_policy_trust_ambiguous",
        ),
        (
            custom_authenticity_kwargs(
                trust_keys=(replace(trust_key(), canonical_digest="f" * 64),)
            ),
            "itsm_sandbox_onboarding_policy_trust_integrity_failed",
        ),
        (
            custom_authenticity_kwargs(
                trust_keys=(trust_key(organization_id="organization.foreign"),)
            ),
            "itsm_sandbox_onboarding_policy_trust_binding_invalid",
        ),
        (
            custom_authenticity_kwargs(
                trust_keys=(trust_key(expires_at=NOW + timedelta(days=29)),)
            ),
            "itsm_sandbox_onboarding_policy_trust_binding_invalid",
        ),
        (
            custom_authenticity_kwargs(
                trust_keys=(
                    trust_key(
                        not_before=NOW + timedelta(hours=1),
                        expires_at=NOW + timedelta(hours=2),
                    ),
                )
            ),
            "itsm_sandbox_onboarding_policy_trust_not_effective",
        ),
        (
            custom_authenticity_kwargs(
                trust_keys=(
                    trust_key(
                        not_before=NOW - timedelta(hours=2),
                        expires_at=NOW - timedelta(hours=1),
                    ),
                )
            ),
            "itsm_sandbox_onboarding_policy_trust_expired",
        ),
        (
            custom_authenticity_kwargs(
                trust_keys=(trust_key(state=ItsmSandboxOnboardingPolicyTrustKeyState.DISABLED),)
            ),
            "itsm_sandbox_onboarding_policy_trust_disabled",
        ),
        (
            custom_authenticity_kwargs(
                trust_keys=(trust_key(state=ItsmSandboxOnboardingPolicyTrustKeyState.REVOKED),)
            ),
            "itsm_sandbox_onboarding_policy_trust_revoked",
        ),
    ],
)
async def test_sandbox_onboarding_policy_trust_fails_closed(
    auth_kwargs: dict[str, Any],
    expected_error: str,
) -> None:
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_onboarding_policy_source=policy_source(),
        **auth_kwargs,
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]

    with pytest.raises(ItsmIntegrationError, match=expected_error):
        await service.sandbox_onboarding_readiness(
            actor=actor(),
            profile_id=profile.profile_id,
            correlation_id="correlation.itsm.sandbox.onboarding.trust-failure",
        )


@pytest.mark.asyncio
async def test_sandbox_onboarding_policy_enforces_evidence_and_conformance_age() -> None:
    current_time = [NOW]
    governed_policy = policy(
        max_conformance_age_seconds=60,
        max_evidence_age_seconds=60,
    )
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_conformance_adapter=ProductionEligibleSandboxAdapter(),
        sandbox_onboarding_evidence_source=ApprovedSandboxOnboardingEvidenceSource(),
        sandbox_onboarding_policy_source=InMemoryItsmSandboxOnboardingPolicySource(
            (governed_policy,)
        ),
        **authenticity_kwargs(governed_policy),
        clock=lambda: current_time[0],
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    await service.assess_sandbox_conformance(
        actor=actor(),
        profile_id=profile.profile_id,
        expected_profile_version=profile.version,
        acknowledged_diagnostic_only_and_no_dispatch=True,
        idempotency_key="itsm-sandbox-onboarding-policy-age",
        correlation_id="correlation.itsm.sandbox.onboarding.policy-age.assess",
    )
    current_time[0] = NOW + timedelta(seconds=61)

    dossier = await service.sandbox_onboarding_readiness(
        actor=actor(),
        profile_id=profile.profile_id,
        correlation_id="correlation.itsm.sandbox.onboarding.policy-age.read",
    )

    assert dossier.state is ItsmSandboxOnboardingState.BLOCKED
    assert {item.reason_code for item in dossier.requirements} >= {
        "itsm.sandbox-onboarding.conformance_stale_by_policy",
        "itsm.sandbox-onboarding.evidence_stale_by_policy",
    }


@pytest.mark.asyncio
async def test_sandbox_onboarding_policy_requires_exact_adapter_identity_and_version() -> None:
    governed_policy = policy(
        adapter_rules=(
            ItsmSandboxOnboardingAdapterRule(
                adapter_id="adapter.itsm.approved-production",
                adapter_version="version.9",
            ),
        )
    )
    service = ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        sandbox_conformance_adapter=ProductionEligibleSandboxAdapter(),
        sandbox_onboarding_evidence_source=ApprovedSandboxOnboardingEvidenceSource(),
        sandbox_onboarding_policy_source=InMemoryItsmSandboxOnboardingPolicySource(
            (governed_policy,)
        ),
        **authenticity_kwargs(governed_policy),
        clock=lambda: NOW,
    )
    profile = await service.create(actor=actor(), **create_values())  # type: ignore[arg-type]
    await service.assess_sandbox_conformance(
        actor=actor(),
        profile_id=profile.profile_id,
        expected_profile_version=profile.version,
        acknowledged_diagnostic_only_and_no_dispatch=True,
        idempotency_key="itsm-sandbox-onboarding-policy-adapter",
        correlation_id="correlation.itsm.sandbox.onboarding.policy-adapter.assess",
    )

    dossier = await service.sandbox_onboarding_readiness(
        actor=actor(),
        profile_id=profile.profile_id,
        correlation_id="correlation.itsm.sandbox.onboarding.policy-adapter.read",
    )

    adapter_requirement = next(
        item
        for item in dossier.requirements
        if item.requirement_id == "itsm.sandbox-onboarding.adapter-sandbox-approved"
    )
    assert adapter_requirement.reason_code == (
        "itsm.sandbox-onboarding.adapter_not_onboarding_eligible"
    )
    assert dossier.sandbox_onboarding_ready is False
