from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel


def _ids(*values: str) -> bool:
    return all(3 <= len(value.strip()) <= 256 for value in values)


def _digests(*values: str) -> bool:
    return all(
        len(value) == 64 and all(char in "0123456789abcdef" for char in value) for value in values
    )


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationCandidatePolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_presentation_schema: str
    required_presentation_state: str
    required_candidate_set_schema: str
    required_receipt_schema: str
    required_generator_id: str
    required_generator_attestor_id: str
    required_categories: tuple[str, ...]
    allowed_capability_ids: tuple[str, ...]
    maximum_capability_class: str
    maximum_authentication_age_minutes: int
    maximum_candidate_count: int
    maximum_steps_per_candidate: int
    maximum_title_characters: int
    maximum_outcome_characters: int
    maximum_text_items_per_candidate: int
    maximum_output_bytes: int
    retention_minutes: int
    prohibited_output_profile_digest: str
    browser_binding_key_digest: str
    classification_ceiling: str
    required_assurance_level: AssuranceLevel
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _ids(
                self.policy_id,
                self.schema_version,
                self.organization_id,
                self.environment_id,
                self.required_presentation_schema,
                self.required_presentation_state,
                self.required_candidate_set_schema,
                self.required_receipt_schema,
                self.required_generator_id,
                self.required_generator_attestor_id,
                self.signed_by,
            )
            or len(set(self.required_categories)) != len(self.required_categories)
            or len(set(self.allowed_capability_ids)) != len(self.allowed_capability_ids)
            or not 3 <= len(self.required_categories) <= 5
            or self.maximum_capability_class not in {"C0", "C1"}
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 3 <= self.maximum_candidate_count <= 5
            or not 1 <= self.maximum_steps_per_candidate <= 10
            or not 20 <= self.maximum_title_characters <= 500
            or not 20 <= self.maximum_outcome_characters <= 2_000
            or not 1 <= self.maximum_text_items_per_candidate <= 100
            or not 1_024 <= self.maximum_output_bytes <= 1_000_000
            or not 1 <= self.retention_minutes <= 1_440
            or not _digests(
                self.prohibited_output_profile_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not self.signature_verified
        ):
            raise ValueError("Protected recommendation-candidate policy is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationCandidateInstruction:
    candidate_set_id: str
    presentation_id: str
    presentation_digest: str
    answer_digest: str
    adjudication_id: str
    adjudication_digest: str
    invocation_id: str
    invocation_digest: str
    context_id: str
    context_digest: str
    context_package_digest: str
    draft_digest: str
    report_digest: str
    organization_id: str
    environment_id: str
    consumer_subject_digest: str
    generation_authorization_digest: str
    policy_id: str
    policy_digest: str
    required_candidate_set_schema: str
    required_categories: tuple[str, ...]
    allowed_capability_ids: tuple[str, ...]
    maximum_capability_class: str
    maximum_candidate_count: int
    maximum_steps_per_candidate: int
    maximum_title_characters: int
    maximum_outcome_characters: int
    maximum_text_items_per_candidate: int
    maximum_output_bytes: int
    prohibited_output_profile_digest: str
    requested_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationCandidateStep:
    order: int
    phase: str
    conceptual_action: str
    capability_id: str | None
    capability_class: str
    executable_by_atlas: bool = False

    def __post_init__(self) -> None:
        if (
            self.order < 1
            or not _ids(self.phase)
            or not 10 <= len(self.conceptual_action.strip()) <= 2_000
            or self.capability_class not in {"C0", "C1"}
            or self.executable_by_atlas
        ):
            raise ValueError("Protected recommendation-candidate step is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationCandidate:
    candidate_id: str
    version: int
    category: str
    state: str
    title: str
    intended_outcome: str
    steps: tuple[ProtectedRecommendationCandidateStep, ...]
    supporting_citation_references: tuple[str, ...]
    contradicting_citation_references: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    applicability_limits: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    confidence: str
    confidence_rationale: str
    service_impact_analyzed: bool = False
    risk_completed: bool = False
    recovery_completed: bool = False
    policy_evaluated: bool = False
    preferred: bool = False
    ready_for_review: bool = False
    execution_authorized: bool = False
    canonical_digest: str = ""

    def __post_init__(self) -> None:
        flags = (
            self.service_impact_analyzed,
            self.risk_completed,
            self.recovery_completed,
            self.policy_evaluated,
            self.preferred,
            self.ready_for_review,
            self.execution_authorized,
        )
        if (
            self.version != 1
            or not _ids(self.candidate_id, self.category, self.state)
            or self.state not in {"candidate-state.provisional", "candidate-state.blocked"}
            or not 10 <= len(self.title.strip()) <= 500
            or not 10 <= len(self.intended_outcome.strip()) <= 2_000
            or not self.steps
            or tuple(step.order for step in self.steps) != tuple(range(1, len(self.steps) + 1))
            or not self.supporting_citation_references
            or not self.unknowns
            or not self.evidence_gaps
            or self.confidence not in {"confidence.low", "confidence.moderate"}
            or not self.confidence_rationale.strip()
            or any(flags)
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Protected recommendation candidate is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationCandidateSet:
    candidate_set_id: str
    schema_version: str
    version: int
    presentation_id: str
    presentation_digest: str
    answer_digest: str
    source_binding_digest: str
    policy_digest: str
    candidates: tuple[ProtectedRecommendationCandidate, ...]
    citation_set_digest: str
    unknown_set_digest: str
    safety_digest: str
    byte_count: int
    generated_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _ids(self.candidate_set_id, self.schema_version, self.presentation_id)
            or not 3 <= len(self.candidates) <= 5
            or len({item.candidate_id for item in self.candidates}) != len(self.candidates)
            or self.byte_count < 1
            or self.generated_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.generated_at < self.expires_at
            or not _digests(
                self.presentation_digest,
                self.answer_digest,
                self.source_binding_digest,
                self.policy_digest,
                self.citation_set_digest,
                self.unknown_set_digest,
                self.safety_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Protected recommendation-candidate set is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationCandidateReceipt:
    candidate_set_id: str
    schema_version: str
    version: int
    generator_id: str
    attested_by: str
    presentation_id: str
    presentation_digest: str
    generation_authorization_digest: str
    policy_digest: str
    candidate_set_digest: str
    source_binding_digest: str
    citation_set_digest: str
    unknown_set_digest: str
    safety_digest: str
    cleanup_digest: str
    candidate_count: int
    step_count: int
    citation_count: int
    unknown_count: int
    byte_count: int
    generated_at: datetime
    expires_at: datetime
    source_verified: bool
    diversity_verified: bool
    citations_verified: bool
    unknowns_preserved: bool
    capability_boundary_verified: bool
    non_executable_verified: bool
    no_preference_assigned: bool
    no_model_used: bool
    cleanup_verified: bool
    signature_verified: bool
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationCandidateClaim:
    claim_id: str
    schema_version: str
    version: int
    candidate_set_id: str
    presentation_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationCandidateRecord:
    candidate_set_id: str
    schema_version: str
    version: int
    claim_id: str
    presentation_id: str
    presentation_digest: str
    answer_digest: str
    adjudication_id: str
    adjudication_digest: str
    invocation_id: str
    invocation_digest: str
    context_id: str
    context_digest: str
    context_package_digest: str
    draft_digest: str
    report_digest: str
    organization_id: str
    environment_id: str
    classification: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    generation_policy_id: str
    generation_policy_digest: str
    generation_policy_version: str
    generator_id: str
    generation_receipt_digest: str
    generation_authorization_digest: str
    candidate_content_digest: str
    source_binding_digest: str
    citation_set_digest: str
    unknown_set_digest: str
    safety_digest: str
    cleanup_digest: str
    candidate_categories: tuple[str, ...]
    maximum_capability_class: str
    candidate_count: int
    step_count: int
    citation_count: int
    unknown_count: int
    byte_count: int
    generated_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    recommendation_candidates_generated: bool = True
    service_impact_analyzed: bool = False
    recommendation_complete: bool = False
    recommendation_presented: bool = False
    recommendation_ready_for_review: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        later = (
            self.service_impact_analyzed,
            self.recommendation_complete,
            self.recommendation_presented,
            self.recommendation_ready_for_review,
            self.recommendation_approved,
            self.workflow_created,
            self.execution_authorized,
            self.deployment_authorized,
            self.infrastructure_mutated,
        )
        if (
            self.version != 1
            or self.instance_state != "protected_recommendation_candidates_generated"
            or not self.recommendation_candidates_generated
            or any(later)
            or self.maximum_capability_class not in {"C0", "C1"}
            or not 3 <= self.candidate_count <= 5
            or self.step_count < self.candidate_count
            or self.citation_count < 1
            or self.unknown_count < 1
            or self.byte_count < 1
            or len(self.candidate_categories) != self.candidate_count
            or not 20 <= len(self.purpose.strip()) <= 1_000
            or self.generated_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.generated_at < self.expires_at
        ):
            raise ValueError("Protected recommendation-candidate record is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationCandidateManifest:
    candidate_set_id: str
    presentation_id: str
    adjudication_id: str
    invocation_id: str
    context_id: str
    candidate_categories: tuple[str, ...]
    maximum_capability_class: str
    candidate_count: int
    step_count: int
    citation_count: int
    unknown_count: int
    byte_count: int
    candidate_content_digest: str
    source_binding_digest: str
    citation_set_digest: str
    unknown_set_digest: str
    safety_digest: str
    cleanup_digest: str
    generated_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationCandidateResult:
    record: ProtectedRecommendationCandidateRecord
    manifest: ProtectedRecommendationCandidateManifest
