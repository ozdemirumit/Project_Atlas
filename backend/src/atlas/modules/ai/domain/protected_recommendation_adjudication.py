from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def _aware(*values: datetime) -> bool:
    return all(value.tzinfo is not None for value in values)


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationAdjudicationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_completion_schema: str
    required_completion_state: str
    required_report_schema: str
    required_receipt_schema: str
    required_adjudicator_id: str
    required_adjudicator_attestor_id: str
    required_dimensions: tuple[str, ...]
    category_precedence: tuple[str, ...]
    allowed_categories: tuple[str, ...]
    maximum_capability_class: str
    maximum_candidate_count: int
    maximum_dimension_count: int
    maximum_exclusion_count: int
    maximum_unknown_count: int
    maximum_output_bytes: int
    retention_minutes: int
    browser_binding_key_digest: str
    preference_profile_digest: str
    safety_profile_digest: str
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _aware(self.issued_at, self.expires_at)
            or self.expires_at <= self.issued_at
            or not self.required_dimensions
            or len(set(self.required_dimensions)) != len(self.required_dimensions)
            or not self.category_precedence
            or set(self.category_precedence) != set(self.allowed_categories)
            or self.maximum_capability_class not in {"C0", "C1"}
            or min(
                self.maximum_candidate_count,
                self.maximum_dimension_count,
                self.maximum_output_bytes,
                self.retention_minutes,
            )
            < 1
            or self.maximum_exclusion_count < 0
            or self.maximum_unknown_count < 0
        ):
            raise ValueError("invalid protected recommendation adjudication policy")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationAdjudicationInstruction:
    adjudication_id: str
    completion_id: str
    completion_digest: str
    candidate_set_id: str
    candidate_set_digest: str
    adjudication_authorization_digest: str
    policy_id: str
    policy_digest: str
    required_dimensions: tuple[str, ...]
    category_precedence: tuple[str, ...]
    allowed_categories: tuple[str, ...]
    maximum_capability_class: str
    maximum_candidate_count: int
    maximum_dimension_count: int
    maximum_exclusion_count: int
    maximum_unknown_count: int
    maximum_output_bytes: int
    required_report_schema: str
    preference_profile_digest: str
    safety_profile_digest: str
    requested_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not _aware(self.requested_at, self.expires_at) or self.expires_at <= self.requested_at:
            raise ValueError("invalid protected adjudication instruction window")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationComparisonDimension:
    dimension: str
    precedence: int
    value: str
    rationale: str
    canonical_digest: str

    def __post_init__(self) -> None:
        if self.precedence < 1 or not all((self.dimension, self.value, self.rationale)):
            raise ValueError("invalid protected recommendation comparison dimension")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationAdjudicationEntry:
    candidate_id: str
    candidate_digest: str
    completion_entry_digest: str
    eligible: bool
    exclusion_reasons: tuple[str, ...]
    dimensions: tuple[ProtectedRecommendationComparisonDimension, ...]
    preference_state: str
    preference_rationale: str
    gap_count: int
    unknown_count: int
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.preference_state not in {"preferred", "alternative", "ineligible"}
            or (self.eligible and self.exclusion_reasons)
            or (not self.eligible and not self.exclusion_reasons)
            or (self.preference_state == "ineligible") == self.eligible
            or self.gap_count < 0
            or self.unknown_count < 0
            or not self.dimensions
        ):
            raise ValueError("invalid protected recommendation adjudication entry")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationAdjudicationReport:
    adjudication_id: str
    schema_version: str
    version: int
    completion_id: str
    completion_digest: str
    candidate_set_id: str
    candidate_set_digest: str
    policy_digest: str
    entries: tuple[ProtectedRecommendationAdjudicationEntry, ...]
    candidate_count: int
    dimension_count: int
    eligible_count: int
    excluded_count: int
    preferred_count: int
    alternative_count: int
    tie: bool
    no_supportable_candidate: bool
    comparison_digest: str
    eligibility_digest: str
    exclusion_digest: str
    preference_digest: str
    safety_digest: str
    byte_count: int
    completed_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _aware(self.completed_at, self.expires_at)
            or self.expires_at <= self.completed_at
            or self.candidate_count != len(self.entries)
            or self.eligible_count + self.excluded_count != self.candidate_count
            or self.preferred_count > 1
            or self.preferred_count + self.alternative_count != self.eligible_count
            or (self.tie and self.preferred_count)
            or self.no_supportable_candidate != (self.eligible_count == 0)
        ):
            raise ValueError("invalid protected recommendation adjudication report")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationAdjudicationReceipt:
    adjudication_id: str
    schema_version: str
    version: int
    adjudicator_id: str
    attested_by: str
    completion_id: str
    completion_digest: str
    candidate_set_id: str
    candidate_set_digest: str
    adjudication_authorization_digest: str
    policy_digest: str
    report_digest: str
    comparison_digest: str
    eligibility_digest: str
    exclusion_digest: str
    preference_digest: str
    safety_digest: str
    cleanup_digest: str
    candidate_count: int
    dimension_count: int
    eligible_count: int
    excluded_count: int
    preferred_count: int
    alternative_count: int
    tie: bool
    no_supportable_candidate: bool
    byte_count: int
    completed_at: datetime
    expires_at: datetime
    source_verified: bool
    complete_candidate_coverage_verified: bool
    deterministic_policy_verified: bool
    conservative_unknowns_verified: bool
    tie_behavior_verified: bool
    no_caller_preference_verified: bool
    no_model_used: bool
    cleanup_verified: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        checks = (
            self.source_verified,
            self.complete_candidate_coverage_verified,
            self.deterministic_policy_verified,
            self.conservative_unknowns_verified,
            self.tie_behavior_verified,
            self.no_caller_preference_verified,
            self.no_model_used,
            self.cleanup_verified,
            self.signature_verified,
        )
        if self.version != 1 or not all(checks) or not _aware(self.completed_at, self.expires_at):
            raise ValueError("invalid protected recommendation adjudication receipt")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationAdjudicationClaim:
    claim_id: str
    schema_version: str
    version: int
    adjudication_id: str
    completion_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if self.version != 1 or not _aware(self.claimed_at):
            raise ValueError("invalid protected recommendation adjudication claim")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationAdjudicationRecord:
    adjudication_id: str
    schema_version: str
    version: int
    claim_id: str
    completion_id: str
    completion_digest: str
    impact_analysis_id: str
    candidate_set_id: str
    candidate_set_digest: str
    presentation_id: str
    organization_id: str
    environment_id: str
    classification: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    adjudication_policy_id: str
    adjudication_policy_digest: str
    adjudication_policy_version: str
    adjudicator_id: str
    adjudication_receipt_digest: str
    adjudication_authorization_digest: str
    protected_report_digest: str
    candidate_count: int
    dimension_count: int
    eligible_count: int
    excluded_count: int
    preferred_count: int
    alternative_count: int
    tie: bool
    no_supportable_candidate: bool
    maximum_risk: str
    interruption_possible_count: int
    recovery_feasible_count: int
    gap_count: int
    unknown_count: int
    comparison_digest: str
    eligibility_digest: str
    exclusion_digest: str
    preference_digest: str
    safety_digest: str
    cleanup_digest: str
    byte_count: int
    adjudicated_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    safety_notice: str
    canonical_digest: str
    service_impact_analyzed: bool = True
    impact_complete: bool = True
    interruption_established: bool = True
    duration_established: bool = True
    risk_completed: bool = True
    recovery_completed: bool = True
    recommendation_complete: bool = True
    recommendation_presented: bool = False
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
            or not _aware(self.adjudicated_at, self.expires_at)
            or self.expires_at <= self.adjudicated_at
            or self.candidate_count < 1
            or self.eligible_count + self.excluded_count != self.candidate_count
            or self.preferred_count > 1
            or self.preferred_count + self.alternative_count != self.eligible_count
            or (self.tie and self.preferred_count)
            or self.no_supportable_candidate != (self.eligible_count == 0)
            or not all(
                (
                    self.service_impact_analyzed,
                    self.impact_complete,
                    self.interruption_established,
                    self.duration_established,
                    self.risk_completed,
                    self.recovery_completed,
                    self.recommendation_complete,
                )
            )
            or any(
                (
                    self.recommendation_presented,
                    self.recommendation_ready_for_review,
                    self.recommendation_approved,
                    self.workflow_created,
                    self.execution_authorized,
                    self.deployment_authorized,
                    self.infrastructure_mutated,
                )
            )
        ):
            raise ValueError("invalid protected recommendation adjudication record")


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationAdjudicationManifest:
    adjudication_id: str
    completion_id: str
    candidate_set_id: str
    candidate_count: int
    dimension_count: int
    eligible_count: int
    excluded_count: int
    preferred_count: int
    alternative_count: int
    tie: bool
    no_supportable_candidate: bool
    maximum_risk: str
    interruption_possible_count: int
    recovery_feasible_count: int
    gap_count: int
    unknown_count: int
    comparison_digest: str
    eligibility_digest: str
    exclusion_digest: str
    preference_digest: str
    safety_digest: str
    adjudicated_at: datetime
    expires_at: datetime
    safety_notice: str


@dataclass(frozen=True, slots=True)
class ProtectedRecommendationAdjudicationResult:
    record: ProtectedRecommendationAdjudicationRecord
    manifest: ProtectedRecommendationAdjudicationManifest
