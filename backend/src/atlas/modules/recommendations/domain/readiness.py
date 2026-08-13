from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel


def _aware(*values: datetime) -> bool:
    return all(value.tzinfo is not None for value in values)


@dataclass(frozen=True, slots=True)
class RecommendationReadinessPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_source_schema: str
    required_source_state: str
    required_evaluator_id: str
    required_evaluator_attestor_id: str
    required_receipt_schema: str
    assessment_schema: str
    allowed_outcomes: tuple[str, ...]
    required_check_ids: tuple[str, ...]
    allowed_reason_codes: tuple[str, ...]
    maximum_option_count: int
    maximum_reason_count: int
    retention_minutes: int
    browser_binding_key_digest: str
    readiness_profile_digest: str
    prohibited_content_profile_digest: str
    required_assurance_level: AssuranceLevel
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _aware(self.issued_at, self.expires_at)
            or self.expires_at <= self.issued_at
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or set(self.allowed_outcomes) != {"preferred", "tie", "no_support"}
            or not self.required_check_ids
            or not self.allowed_reason_codes
            or min(
                self.maximum_option_count,
                self.maximum_reason_count,
                self.retention_minutes,
            )
            < 1
        ):
            raise ValueError("invalid recommendation readiness policy")


@dataclass(frozen=True, slots=True)
class RecommendationReadinessInstruction:
    assessment_id: str
    recommendation_id: str
    recommendation_digest: str
    promotion_id: str
    organization_id: str
    environment_id: str
    consumer_subject_digest: str
    readiness_authorization_digest: str
    policy_id: str
    policy_digest: str
    assessment_schema: str
    required_check_ids: tuple[str, ...]
    allowed_reason_codes: tuple[str, ...]
    maximum_reason_count: int
    readiness_profile_digest: str
    prohibited_content_profile_digest: str
    requested_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not _aware(self.requested_at, self.expires_at) or self.expires_at <= self.requested_at:
            raise ValueError("invalid recommendation readiness instruction")


@dataclass(frozen=True, slots=True)
class RecommendationReadinessReceipt:
    assessment_id: str
    schema_version: str
    version: int
    evaluator_id: str
    attested_by: str
    recommendation_id: str
    recommendation_digest: str
    policy_digest: str
    readiness_authorization_digest: str
    assessment_digest: str
    source_binding_digest: str
    evaluation_outcome: str
    check_count: int
    passed_check_count: int
    reason_count: int
    assessed_at: datetime
    expires_at: datetime
    source_verified: bool
    outcome_preserved: bool
    deterministic_evaluation: bool
    no_model_used: bool
    no_network_used: bool
    no_operational_authority: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or self.evaluation_outcome not in {"ready", "blocked"}
            or self.check_count < 1
            or not 0 <= self.passed_check_count <= self.check_count
            or self.reason_count < 0
            or (self.evaluation_outcome == "ready")
            != (self.passed_check_count == self.check_count and self.reason_count == 0)
            or not _aware(self.assessed_at, self.expires_at)
            or self.expires_at <= self.assessed_at
            or not all(
                (
                    self.source_verified,
                    self.outcome_preserved,
                    self.deterministic_evaluation,
                    self.no_model_used,
                    self.no_network_used,
                    self.no_operational_authority,
                    self.signature_verified,
                )
            )
        ):
            raise ValueError("invalid recommendation readiness receipt")


@dataclass(frozen=True, slots=True)
class RecommendationReadinessClaim:
    claim_id: str
    schema_version: str
    version: int
    assessment_id: str
    recommendation_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class RecommendationReadinessAssessment:
    assessment_id: str
    recommendation_id: str
    schema_version: str
    version: int
    claim_id: str
    promotion_id: str
    presentation_id: str
    organization_id: str
    environment_id: str
    classification: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    readiness_policy_id: str
    readiness_policy_digest: str
    readiness_policy_version: str
    evaluator_id: str
    readiness_receipt_digest: str
    readiness_authorization_digest: str
    source_artifact_digest: str
    source_binding_digest: str
    source_outcome: str
    option_count: int
    preferred_count: int
    evaluation_outcome: str
    reason_codes: tuple[str, ...]
    check_count: int
    passed_check_count: int
    state: str
    assessed_at: datetime
    expires_at: datetime
    purpose: str
    canonical_digest: str
    recommendation_ready_for_review: bool
    human_review_completed: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    itsm_record_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        ready = self.evaluation_outcome == "ready"
        if (
            self.version != 1
            or self.source_outcome not in {"preferred", "tie", "no_support"}
            or self.evaluation_outcome not in {"ready", "blocked"}
            or self.option_count < 1
            or self.preferred_count not in {0, 1}
            or (self.source_outcome == "preferred") != (self.preferred_count == 1)
            or self.check_count < 1
            or not 0 <= self.passed_check_count <= self.check_count
            or ready != (self.passed_check_count == self.check_count and not self.reason_codes)
            or self.state != ("ready_for_review" if ready else "blocked")
            or self.recommendation_ready_for_review != ready
            or not _aware(self.assessed_at, self.expires_at)
            or self.expires_at <= self.assessed_at
            or any(
                (
                    self.human_review_completed,
                    self.recommendation_approved,
                    self.workflow_created,
                    self.itsm_record_created,
                    self.execution_authorized,
                    self.deployment_authorized,
                    self.infrastructure_mutated,
                )
            )
        ):
            raise ValueError("invalid recommendation readiness assessment")


@dataclass(frozen=True, slots=True)
class RecommendationReadinessManifest:
    assessment_id: str
    recommendation_id: str
    promotion_id: str
    source_outcome: str
    option_count: int
    preferred_count: int
    evaluation_outcome: str
    reason_codes: tuple[str, ...]
    check_count: int
    passed_check_count: int
    state: str
    assessed_at: datetime
    expires_at: datetime
    recommendation_ready_for_review: bool


@dataclass(frozen=True, slots=True)
class RecommendationReadinessResult:
    assessment: RecommendationReadinessAssessment
    manifest: RecommendationReadinessManifest
