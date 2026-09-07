from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.itsm.domain.dispatch import (
    ItsmOutboundDispatchAuthorization,
    authorize_outbound_dispatch,
)
from atlas.modules.itsm.domain.models import (
    ITSM_SANDBOX_ONBOARDING_REQUIREMENTS,
    ItsmAllowedOperation,
    ItsmCheckState,
    ItsmFieldMapping,
    ItsmIntegrationProfile,
    ItsmProfileLifecycle,
    ItsmProviderFamily,
    ItsmReadinessAssessment,
    ItsmReadinessCheck,
    ItsmReadinessState,
    ItsmSandboxOnboardingReadiness,
    ItsmSandboxOnboardingRequirement,
    ItsmSandboxOnboardingRequirementState,
    ItsmSandboxOnboardingState,
    ItsmWriteSemantics,
)
from atlas.modules.reports.domain.models import (
    HandoffState,
    ItsmHandoffDraft,
    RedactionState,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
_DIGEST = "a" * 64
_OTHER_DIGEST = "b" * 64


def _readiness_assessment() -> ItsmReadinessAssessment:
    checks = tuple(
        ItsmReadinessCheck(
            check_id=f"check.{index}", state=ItsmCheckState.SATISFIED, reason_code="itsm.ok"
        )
        for index in range(6)
    )
    return ItsmReadinessAssessment(
        state=ItsmReadinessState.READY_FOR_SANDBOX,
        checks=checks,
        assessed_at=NOW,
        canonical_digest=_DIGEST,
    )


def _profile(**overrides: object) -> ItsmIntegrationProfile:
    defaults: dict[str, object] = {
        "profile_id": "profile.example-001",
        "schema_version": "atlas.itsm-integration-profile.v1",
        "version": 1,
        "organization_id": "organization.example",
        "environment_id": "environment.prod",
        "site_id": "site.primary",
        "profile_key": "example.profile",
        "display_name": "Example ITSM Profile",
        "provider_family": ItsmProviderFamily.SERVICE_NOW,
        "instance_reference": "instance.example",
        "owner_id": "subject.owner",
        "purpose": "Governed ITSM integration for incident analysis handoff.",
        "endpoint_origin": "https://example.service-now.com",
        "trust_boundary_reference": "trust.example-001",
        "secret_reference_id": "secret.example-001",
        "classification_ceiling": DataClassification.INTERNAL,
        "allowed_operations": (
            ItsmAllowedOperation.APPEND_ANALYSIS,
            ItsmAllowedOperation.CREATE_INCIDENT_DRAFT,
        ),
        "mapping_version": 1,
        "field_mappings": (
            ItsmFieldMapping(
                source_field="work_notes",
                provider_field="work_notes",
                write_semantics=ItsmWriteSemantics.APPEND_ONLY,
            ),
        ),
        "sandbox_validation_reference": None,
        "sandbox_validation_digest": None,
        "audit_profile_id": "audit.example-001",
        "lifecycle": ItsmProfileLifecycle.ACTIVE,
        "readiness": _readiness_assessment(),
        "created_by": "subject.owner",
        "created_at": NOW,
        "updated_by": "subject.owner",
        "updated_at": NOW,
        "canonical_digest": _DIGEST,
        "create_request_fingerprint": _DIGEST,
        "create_idempotency_key": "idempotency-key-001",
    }
    defaults.update(overrides)
    return ItsmIntegrationProfile(**defaults)  # type: ignore[arg-type]


def _onboarding_readiness(**overrides: object) -> ItsmSandboxOnboardingReadiness:
    requirements = tuple(
        ItsmSandboxOnboardingRequirement(
            requirement_id=requirement_id,
            state=ItsmSandboxOnboardingRequirementState.SATISFIED,
            reason_code=requirement_id,
        )
        for requirement_id in ITSM_SANDBOX_ONBOARDING_REQUIREMENTS
    )
    defaults: dict[str, object] = {
        "schema_version": "atlas.itsm-sandbox-onboarding-readiness.v3",
        "version": 1,
        "organization_id": "organization.example",
        "environment_id": "environment.prod",
        "site_id": "site.primary",
        "profile_id": "profile.example-001",
        "profile_version": 1,
        "profile_digest": _DIGEST,
        "mapping_version": 1,
        "conformance_assessment_id": None,
        "conformance_assessment_digest": None,
        "adapter_id": None,
        "adapter_version": None,
        "policy_id": "policy.example-001",
        "policy_version": 1,
        "policy_digest": _DIGEST,
        "policy_issuer": "issuer.example",
        "policy_expires_at": NOW + timedelta(days=1),
        "policy_provenance_id": "provenance.example-001",
        "policy_provenance_digest": _DIGEST,
        "policy_signing_key_id": "signing-key.example-001",
        "policy_signing_key_version": "signing-key-version.1",
        "policy_signature_algorithm": "algorithm.example",
        "policy_signed_at": NOW - timedelta(hours=1),
        "policy_verified_at": NOW,
        "assessed_at": NOW,
        "evidence_observed_at": None,
        "evidence_valid_until": None,
        "state": ItsmSandboxOnboardingState.READY,
        "requirements": requirements,
        "canonical_digest": _OTHER_DIGEST,
        "sandbox_onboarding_ready": True,
    }
    defaults.update(overrides)
    return ItsmSandboxOnboardingReadiness(**defaults)  # type: ignore[arg-type]


def _draft(**overrides: object) -> ItsmHandoffDraft:
    defaults: dict[str, object] = {
        "draft_id": "draft.example-001",
        "idempotency_key": "idempotency.draft-001",
        "state": HandoffState.REVIEW_REQUIRED,
        "external_system": "service_now.example",
        "operation": "append_analysis",
        "incident_reference": "incident.example-001",
        "report_id": "report.example-001",
        "report_version": 1,
        "generated_content_label": "ai-generated",
        "field_mappings": (),
        "artifact_references": ("artifact.example-001",),
        "classification": DataClassification.INTERNAL,
        "redaction_state": RedactionState.COMPLETE,
        "human_review_required": True,
        "dispatch_authorized": False,
        "external_record_mutated": False,
    }
    defaults.update(overrides)
    return ItsmHandoffDraft(**defaults)  # type: ignore[arg-type]


def test_dispatch_authorized_when_every_gate_passes() -> None:
    result = authorize_outbound_dispatch(
        authorization_id="authorization.example-001",
        profile=_profile(),
        onboarding_readiness=_onboarding_readiness(),
        operation=ItsmAllowedOperation.APPEND_ANALYSIS,
        draft=_draft(),
        human_reviewer_id="subject.reviewer",
        human_review_completed_at=NOW,
        decided_at=NOW,
    )
    assert result.dispatch_authorized is True
    assert result.denial_reason is None


def test_dispatch_denied_when_profile_not_active() -> None:
    retired_profile = _profile(
        version=2,
        lifecycle=ItsmProfileLifecycle.RETIRED,
        retired_by="subject.owner",
        retired_at=NOW,
        retirement_reason="Superseded by a newer integration profile.",
        retirement_request_fingerprint=_DIGEST,
        retirement_idempotency_key="retirement-key-001",
    )
    result = authorize_outbound_dispatch(
        authorization_id="authorization.example-001",
        profile=retired_profile,
        onboarding_readiness=_onboarding_readiness(),
        operation=ItsmAllowedOperation.APPEND_ANALYSIS,
        draft=_draft(),
        human_reviewer_id="subject.reviewer",
        human_review_completed_at=NOW,
        decided_at=NOW,
    )
    assert result.dispatch_authorized is False
    assert result.denial_reason == "itsm_dispatch_profile_not_active"


def test_dispatch_denied_when_operation_not_permitted() -> None:
    result = authorize_outbound_dispatch(
        authorization_id="authorization.example-001",
        profile=_profile(),
        onboarding_readiness=_onboarding_readiness(),
        operation=ItsmAllowedOperation.ATTACH_EVIDENCE_PACKAGE,
        draft=_draft(),
        human_reviewer_id="subject.reviewer",
        human_review_completed_at=NOW,
        decided_at=NOW,
    )
    assert result.denial_reason == "itsm_dispatch_operation_not_permitted"


def test_dispatch_denied_when_operation_not_outbound() -> None:
    result = authorize_outbound_dispatch(
        authorization_id="authorization.example-001",
        profile=_profile(allowed_operations=(ItsmAllowedOperation.RETRIEVE_RECORD,)),
        onboarding_readiness=_onboarding_readiness(),
        operation=ItsmAllowedOperation.RETRIEVE_RECORD,
        draft=_draft(),
        human_reviewer_id="subject.reviewer",
        human_review_completed_at=NOW,
        decided_at=NOW,
    )
    assert result.denial_reason == "itsm_dispatch_operation_not_outbound"


def test_dispatch_denied_when_onboarding_not_ready() -> None:
    blocked_requirements = tuple(
        ItsmSandboxOnboardingRequirement(
            requirement_id=requirement_id,
            state=(
                ItsmSandboxOnboardingRequirementState.BLOCKED
                if index == 0
                else ItsmSandboxOnboardingRequirementState.SATISFIED
            ),
            reason_code=requirement_id,
        )
        for index, requirement_id in enumerate(ITSM_SANDBOX_ONBOARDING_REQUIREMENTS)
    )
    result = authorize_outbound_dispatch(
        authorization_id="authorization.example-001",
        profile=_profile(),
        onboarding_readiness=_onboarding_readiness(
            state=ItsmSandboxOnboardingState.BLOCKED,
            sandbox_onboarding_ready=False,
            requirements=blocked_requirements,
        ),
        operation=ItsmAllowedOperation.APPEND_ANALYSIS,
        draft=_draft(),
        human_reviewer_id="subject.reviewer",
        human_review_completed_at=NOW,
        decided_at=NOW,
    )
    assert result.denial_reason == "itsm_dispatch_onboarding_not_ready"


def test_dispatch_denied_when_readiness_profile_mismatch() -> None:
    result = authorize_outbound_dispatch(
        authorization_id="authorization.example-001",
        profile=_profile(),
        onboarding_readiness=_onboarding_readiness(profile_id="profile.someone-else"),
        operation=ItsmAllowedOperation.APPEND_ANALYSIS,
        draft=_draft(),
        human_reviewer_id="subject.reviewer",
        human_review_completed_at=NOW,
        decided_at=NOW,
    )
    assert result.denial_reason == "itsm_dispatch_readiness_profile_mismatch"


def test_dispatch_denied_when_human_review_incomplete() -> None:
    result = authorize_outbound_dispatch(
        authorization_id="authorization.example-001",
        profile=_profile(),
        onboarding_readiness=_onboarding_readiness(),
        operation=ItsmAllowedOperation.APPEND_ANALYSIS,
        draft=_draft(),
        human_reviewer_id=None,
        human_review_completed_at=None,
        decided_at=NOW,
    )
    assert result.denial_reason == "itsm_dispatch_human_review_incomplete"


def test_authorization_type_rejects_authorized_without_reviewer() -> None:
    with pytest.raises(ValueError, match="completed human review"):
        ItsmOutboundDispatchAuthorization(
            authorization_id="authorization.example-001",
            profile_id="profile.example-001",
            operation=ItsmAllowedOperation.APPEND_ANALYSIS,
            draft_id="draft.example-001",
            draft_idempotency_key="idempotency.draft-001",
            human_reviewer_id=None,
            human_review_completed_at=None,
            dispatch_authorized=True,
            denial_reason=None,
            decided_at=NOW,
        )


def test_authorization_type_rejects_mismatched_outcome_and_reason() -> None:
    with pytest.raises(ValueError, match="outcome and denial reason must agree"):
        ItsmOutboundDispatchAuthorization(
            authorization_id="authorization.example-001",
            profile_id="profile.example-001",
            operation=ItsmAllowedOperation.APPEND_ANALYSIS,
            draft_id="draft.example-001",
            draft_idempotency_key="idempotency.draft-001",
            human_reviewer_id="subject.reviewer",
            human_review_completed_at=NOW,
            dispatch_authorized=True,
            denial_reason="some_reason",
            decided_at=NOW,
        )
