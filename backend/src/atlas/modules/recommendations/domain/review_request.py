from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def _aware(*values: datetime) -> bool:
    return all(value.tzinfo is not None for value in values)


@dataclass(frozen=True, slots=True)
class RecommendationReviewRequestPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_source_schema: str
    required_source_state: str
    required_source_outcome: str
    required_adapter_id: str
    required_adapter_attestor_id: str
    required_receipt_schema: str
    request_schema: str
    allowed_source_outcomes: tuple[str, ...]
    track_codes: tuple[str, ...]
    queue_ids: tuple[str, ...]
    routing_profile: str
    sla_class: str
    maximum_track_count: int
    retention_minutes: int
    browser_binding_key_digest: str
    routing_profile_digest: str
    no_authority_profile_digest: str
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or self.required_source_outcome != "ready"
            or set(self.allowed_source_outcomes) != {"preferred", "tie", "no_support"}
            or not self.track_codes
            or len(self.track_codes) != len(self.queue_ids)
            or len(set(self.track_codes)) != len(self.track_codes)
            or len(set(self.queue_ids)) != len(self.queue_ids)
            or len(self.track_codes) > self.maximum_track_count
            or min(self.maximum_track_count, self.retention_minutes) < 1
            or not _aware(self.issued_at, self.expires_at)
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("invalid recommendation review request policy")


@dataclass(frozen=True, slots=True)
class RecommendationReviewRequestInstruction:
    review_request_id: str
    recommendation_id: str
    recommendation_digest: str
    readiness_assessment_id: str
    readiness_assessment_digest: str
    promotion_id: str
    organization_id: str
    environment_id: str
    requester_subject_digest: str
    review_request_authorization_digest: str
    policy_id: str
    policy_digest: str
    request_schema: str
    track_codes: tuple[str, ...]
    queue_ids: tuple[str, ...]
    routing_profile: str
    sla_class: str
    routing_profile_digest: str
    no_authority_profile_digest: str
    requested_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if (
            not self.track_codes
            or len(self.track_codes) != len(self.queue_ids)
            or not _aware(self.requested_at, self.expires_at)
            or self.expires_at <= self.requested_at
        ):
            raise ValueError("invalid recommendation review request instruction")


@dataclass(frozen=True, slots=True)
class RecommendationReviewRequestReceipt:
    review_request_id: str
    schema_version: str
    version: int
    adapter_id: str
    attested_by: str
    recommendation_id: str
    recommendation_digest: str
    readiness_assessment_id: str
    readiness_assessment_digest: str
    policy_digest: str
    review_request_authorization_digest: str
    request_digest: str
    manifest_digest: str
    routing_digest: str
    track_count: int
    requested_at: datetime
    expires_at: datetime
    source_verified: bool
    routing_policy_preserved: bool
    immutable_manifest_confirmed: bool
    deterministic_orchestration: bool
    no_model_used: bool
    no_network_used: bool
    no_reviewer_assigned: bool
    no_operational_authority: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or self.track_count < 1
            or not _aware(self.requested_at, self.expires_at)
            or self.expires_at <= self.requested_at
            or not all(
                (
                    self.source_verified,
                    self.routing_policy_preserved,
                    self.immutable_manifest_confirmed,
                    self.deterministic_orchestration,
                    self.no_model_used,
                    self.no_network_used,
                    self.no_reviewer_assigned,
                    self.no_operational_authority,
                    self.signature_verified,
                )
            )
        ):
            raise ValueError("invalid recommendation review request receipt")


@dataclass(frozen=True, slots=True)
class RecommendationReviewRequestClaim:
    claim_id: str
    schema_version: str
    version: int
    review_request_id: str
    recommendation_id: str
    readiness_assessment_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class RecommendationReviewRequestRecord:
    review_request_id: str
    recommendation_id: str
    schema_version: str
    version: int
    claim_id: str
    readiness_assessment_id: str
    promotion_id: str
    presentation_id: str
    organization_id: str
    environment_id: str
    classification: str
    requester_subject_digest: str
    browser_session_binding_digest: str
    review_request_policy_id: str
    review_request_policy_digest: str
    review_request_policy_version: str
    orchestrator_id: str
    review_request_receipt_digest: str
    review_request_authorization_digest: str
    source_assessment_digest: str
    source_recommendation_digest: str
    source_binding_digest: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_codes: tuple[str, ...]
    queue_ids: tuple[str, ...]
    track_statuses: tuple[tuple[str, str], ...]
    routing_profile: str
    sla_class: str
    manifest_digest: str
    state: str
    requested_at: datetime
    expires_at: datetime
    purpose: str
    canonical_digest: str
    review_requested: bool
    reviewer_assigned: bool = False
    content_inspection_opened: bool = False
    human_review_completed: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    itsm_record_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or self.source_outcome not in {"preferred", "tie", "no_support"}
            or self.option_count < 1
            or self.preferred_count not in {0, 1}
            or (self.source_outcome == "preferred") != (self.preferred_count == 1)
            or not self.track_codes
            or len(self.track_codes) != len(self.queue_ids)
            or self.track_statuses
            != tuple((track, "awaiting_reviewer") for track in self.track_codes)
            or self.state != "review_requested"
            or not self.review_requested
            or not _aware(self.requested_at, self.expires_at)
            or self.expires_at <= self.requested_at
            or any(
                (
                    self.reviewer_assigned,
                    self.content_inspection_opened,
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
            raise ValueError("invalid recommendation review request record")


@dataclass(frozen=True, slots=True)
class RecommendationReviewRequestManifest:
    review_request_id: str
    recommendation_id: str
    readiness_assessment_id: str
    promotion_id: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_codes: tuple[str, ...]
    queue_ids: tuple[str, ...]
    track_statuses: tuple[tuple[str, str], ...]
    routing_profile: str
    sla_class: str
    state: str
    requested_at: datetime
    expires_at: datetime
    review_requested: bool


@dataclass(frozen=True, slots=True)
class RecommendationReviewRequestResult:
    record: RecommendationReviewRequestRecord
    manifest: RecommendationReviewRequestManifest
