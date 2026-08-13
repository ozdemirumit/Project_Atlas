from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel


def _aware(*values: datetime) -> bool:
    return all(value.tzinfo is not None for value in values)


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationPresentationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_adjudication_schema: str
    required_adjudication_state: str
    required_presenter_id: str
    required_presenter_attestor_id: str
    required_receipt_schema: str
    media_type: str
    maximum_option_count: int
    maximum_steps_per_option: int
    maximum_text_items_per_option: int
    maximum_output_bytes: int
    retention_minutes: int
    required_assurance_level: AssuranceLevel
    browser_binding_key_digest: str
    rendering_profile_digest: str
    prohibited_output_profile_digest: str
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _aware(self.issued_at, self.expires_at)
            or self.expires_at <= self.issued_at
            or self.media_type != "text/plain"
            or min(
                self.maximum_option_count,
                self.maximum_steps_per_option,
                self.maximum_text_items_per_option,
                self.maximum_output_bytes,
                self.retention_minutes,
            )
            < 1
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
        ):
            raise ValueError("invalid protected recommendation presentation policy")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationPresentationInstruction:
    presentation_id: str
    adjudication_id: str
    adjudication_digest: str
    adjudication_report_digest: str
    completion_digest: str
    candidate_set_digest: str
    impact_report_digest: str
    completion_report_digest: str
    organization_id: str
    environment_id: str
    consumer_subject_digest: str
    presentation_authorization_digest: str
    policy_id: str
    policy_digest: str
    media_type: str
    maximum_option_count: int
    maximum_steps_per_option: int
    maximum_text_items_per_option: int
    maximum_output_bytes: int
    rendering_profile_digest: str
    prohibited_output_profile_digest: str
    requested_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not _aware(self.requested_at, self.expires_at) or self.expires_at <= self.requested_at:
            raise ValueError("invalid protected recommendation presentation instruction")


@dataclass(frozen=True, slots=True)
class PresentedRecommendationStep:
    order: int
    phase: str
    conceptual_action: str
    capability_class: str


@dataclass(frozen=True, slots=True)
class PresentedRecommendationOption:
    role: str
    category: str
    title: str
    intended_outcome: str
    rationale: str
    confidence: str
    confidence_rationale: str
    steps: tuple[PresentedRecommendationStep, ...]
    overall_risk: str
    work_minimum_minutes: int
    work_maximum_minutes: int
    interruption_expected_mode: str
    interruption_minimum_minutes: int
    interruption_maximum_minutes: int
    recovery_feasibility: str
    recovery_minimum_minutes: int
    recovery_maximum_minutes: int
    technical_service_count: int
    business_service_count: int
    evidence_references: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    applicability_limits: tuple[str, ...]
    support_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            self.role not in {"preferred", "alternative", "tied", "unsupported"}
            or self.capability_class_invalid
            or not self.steps
            or min(
                self.work_minimum_minutes,
                self.work_maximum_minutes,
                self.interruption_minimum_minutes,
                self.interruption_maximum_minutes,
                self.recovery_minimum_minutes,
                self.recovery_maximum_minutes,
                self.technical_service_count,
                self.business_service_count,
            )
            < 0
        ):
            raise ValueError("invalid presented recommendation option")

    @property
    def capability_class_invalid(self) -> bool:
        return any(step.capability_class not in {"C0", "C1"} for step in self.steps)


@dataclass(frozen=True, slots=True)
class ProtectedPresentedRecommendation:
    presentation_id: str
    outcome: str
    headline: str
    safety_notice: str
    options: tuple[PresentedRecommendationOption, ...]
    evidence_needs: tuple[str, ...]
    media_type: str
    byte_count: int
    presented_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.outcome not in {"preferred", "tie", "no_support"}
            or not self.options
            or self.media_type != "text/plain"
            or self.byte_count < 1
            or not _aware(self.presented_at, self.expires_at)
            or self.expires_at <= self.presented_at
            or (self.outcome == "preferred")
            != any(option.role == "preferred" for option in self.options)
            or (self.outcome == "tie" and not all(option.role == "tied" for option in self.options))
            or (
                self.outcome == "no_support"
                and not all(option.role == "unsupported" for option in self.options)
            )
        ):
            raise ValueError("invalid protected presented recommendation")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationPresentationReceipt:
    presentation_id: str
    schema_version: str
    version: int
    presenter_id: str
    attested_by: str
    adjudication_id: str
    adjudication_digest: str
    presentation_authorization_digest: str
    policy_digest: str
    recommendation_digest: str
    source_binding_digest: str
    rendering_digest: str
    cleanup_digest: str
    outcome: str
    option_count: int
    preferred_count: int
    evidence_reference_count: int
    unknown_count: int
    byte_count: int
    presented_at: datetime
    expires_at: datetime
    source_verified: bool
    outcome_preserved: bool
    safe_fields_verified: bool
    inert_rendering_verified: bool
    no_model_used: bool
    no_operational_authority: bool
    cleanup_verified: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or self.outcome not in {"preferred", "tie", "no_support"}
            or self.option_count < 1
            or self.preferred_count not in {0, 1}
            or (self.outcome == "preferred") != (self.preferred_count == 1)
            or min(self.evidence_reference_count, self.unknown_count, self.byte_count) < 0
            or not _aware(self.presented_at, self.expires_at)
            or not all(
                (
                    self.source_verified,
                    self.outcome_preserved,
                    self.safe_fields_verified,
                    self.inert_rendering_verified,
                    self.no_model_used,
                    self.no_operational_authority,
                    self.cleanup_verified,
                    self.signature_verified,
                )
            )
        ):
            raise ValueError("invalid protected recommendation presentation receipt")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationPresentationClaim:
    claim_id: str
    schema_version: str
    version: int
    presentation_id: str
    adjudication_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationPresentationRecord:
    presentation_id: str
    schema_version: str
    version: int
    claim_id: str
    adjudication_id: str
    adjudication_digest: str
    completion_id: str
    candidate_set_id: str
    impact_analysis_id: str
    organization_id: str
    environment_id: str
    classification: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    presentation_policy_id: str
    presentation_policy_digest: str
    presentation_policy_version: str
    presenter_id: str
    presentation_receipt_digest: str
    presentation_authorization_digest: str
    recommendation_digest: str
    source_binding_digest: str
    rendering_digest: str
    cleanup_digest: str
    outcome: str
    option_count: int
    preferred_count: int
    evidence_reference_count: int
    unknown_count: int
    byte_count: int
    media_type: str
    presented_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    safety_notice: str
    canonical_digest: str
    recommendation_presented: bool = True
    recommendation_ready_for_review: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or self.outcome not in {"preferred", "tie", "no_support"}
            or self.option_count < 1
            or self.preferred_count not in {0, 1}
            or self.instance_state != "protected_recommendation_presented"
            or self.media_type != "text/plain"
            or not _aware(self.presented_at, self.expires_at)
            or not self.recommendation_presented
            or any(
                (
                    self.recommendation_ready_for_review,
                    self.recommendation_approved,
                    self.workflow_created,
                    self.execution_authorized,
                    self.deployment_authorized,
                    self.infrastructure_mutated,
                )
            )
        ):
            raise ValueError("invalid protected recommendation presentation record")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationPresentationManifest:
    presentation_id: str
    adjudication_id: str
    completion_id: str
    candidate_set_id: str
    impact_analysis_id: str
    outcome: str
    option_count: int
    preferred_count: int
    evidence_reference_count: int
    unknown_count: int
    byte_count: int
    media_type: str
    recommendation_digest: str
    source_binding_digest: str
    rendering_digest: str
    presented_at: datetime
    expires_at: datetime
    safety_notice: str


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationPresentationResult:
    record: ProtectedRecommendationPresentationRecord
    manifest: ProtectedRecommendationPresentationManifest
    recommendation: ProtectedPresentedRecommendation
