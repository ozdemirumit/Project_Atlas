from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel

TECHNICAL_TRACK = "review-track.technical"
SERVICE_IMPACT_TRACK = "review-track.service-impact"
ASSIGNED = "assigned"


def _aware(*values: datetime) -> bool:
    return all(value.tzinfo is not None for value in values)


@dataclass(frozen=True, slots=True)
class RecommendationReviewerAssignmentPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_source_schema: str
    required_source_state: str
    required_adapter_id: str
    required_adapter_attestor_id: str
    required_receipt_schema: str
    assignment_schema: str
    track_codes: tuple[str, ...]
    queue_ids: tuple[str, ...]
    directory_source_id: str
    directory_source_digest: str
    eligibility_profile_digests: tuple[str, ...]
    subject_digest_salt_digest: str
    routing_profile_digest: str
    separation_profile_digest: str
    maximum_source_age_minutes: int
    assignment_ttl_minutes: int
    retention_minutes: int
    browser_binding_key_digest: str
    required_assurance_level: AssuranceLevel
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or self.track_codes != (TECHNICAL_TRACK, SERVICE_IMPACT_TRACK)
            or len(self.queue_ids) != 2
            or len(set(self.queue_ids)) != 2
            or len(self.eligibility_profile_digests) != 2
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or min(
                self.maximum_source_age_minutes,
                self.assignment_ttl_minutes,
                self.retention_minutes,
            )
            < 1
            or not self.signature_verified
            or not _aware(self.issued_at, self.expires_at)
            or self.expires_at <= self.issued_at
        ):
            raise ValueError("invalid recommendation reviewer assignment policy")


@dataclass(frozen=True, slots=True)
class RecommendationReviewerAssignmentInstruction:
    assignment_set_id: str
    review_request_id: str
    review_request_digest: str
    recommendation_id: str
    readiness_assessment_id: str
    promotion_id: str
    organization_id: str
    environment_id: str
    policy_id: str
    policy_digest: str
    assignment_schema: str
    track_codes: tuple[str, ...]
    queue_ids: tuple[str, ...]
    manifest_digest: str
    directory_source_id: str
    directory_source_digest: str
    eligibility_profile_digests: tuple[str, ...]
    subject_digest_salt_digest: str
    routing_profile_digest: str
    separation_profile_digest: str
    exclusion_subject_digests: tuple[str, ...]
    assignment_ttl_minutes: int
    requested_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if (
            self.track_codes != (TECHNICAL_TRACK, SERVICE_IMPACT_TRACK)
            or len(self.queue_ids) != 2
            or len(self.eligibility_profile_digests) != 2
            or not 2 <= len(self.exclusion_subject_digests) <= 32
            or len(set(self.exclusion_subject_digests)) != len(self.exclusion_subject_digests)
            or self.assignment_ttl_minutes < 1
            or not _aware(self.requested_at, self.expires_at)
            or self.expires_at <= self.requested_at
        ):
            raise ValueError("invalid recommendation reviewer assignment instruction")


@dataclass(frozen=True, slots=True)
class RecommendationReviewerAssignmentReceipt:
    assignment_set_id: str
    schema_version: str
    version: int
    adapter_id: str
    attested_by: str
    review_request_id: str
    review_request_digest: str
    assignment_digest: str
    routing_digest: str
    eligibility_digest: str
    separation_digest: str
    artifact_digest: str
    track_assignments: tuple[tuple[str, str, str, str, str], ...]
    created_at: datetime
    expires_at: datetime
    directory_snapshot_current: bool
    eligibility_verified: bool
    excluded_actors_verified: bool
    distinct_reviewers_verified: bool
    immutable_assignments_confirmed: bool
    encrypted_identity_references: bool
    transient_identity_buffers_erased: bool
    directory_channel_closed: bool
    no_content_opened: bool
    no_model_used: bool
    no_operational_authority: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        tracks = tuple(item[0] for item in self.track_assignments)
        queues = tuple(item[1] for item in self.track_assignments)
        assignment_ids = tuple(item[2] for item in self.track_assignments)
        reviewers = tuple(item[3] for item in self.track_assignments)
        statuses = tuple(item[4] for item in self.track_assignments)
        if (
            self.version != 1
            or tracks != (TECHNICAL_TRACK, SERVICE_IMPACT_TRACK)
            or len(set(queues)) != 2
            or len(set(assignment_ids)) != 2
            or len(set(reviewers)) != 2
            or statuses != (ASSIGNED, ASSIGNED)
            or not _aware(self.created_at, self.expires_at)
            or self.expires_at <= self.created_at
            or not all(
                (
                    self.directory_snapshot_current,
                    self.eligibility_verified,
                    self.excluded_actors_verified,
                    self.distinct_reviewers_verified,
                    self.immutable_assignments_confirmed,
                    self.encrypted_identity_references,
                    self.transient_identity_buffers_erased,
                    self.directory_channel_closed,
                    self.no_content_opened,
                    self.no_model_used,
                    self.no_operational_authority,
                    self.signature_verified,
                )
            )
        ):
            raise ValueError("invalid recommendation reviewer assignment receipt")


@dataclass(frozen=True, slots=True)
class RecommendationReviewerAssignmentClaim:
    claim_id: str
    schema_version: str
    version: int
    assignment_set_id: str
    review_request_id: str
    review_request_digest: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class RecommendationReviewerAssignmentRecord:
    assignment_set_id: str
    schema_version: str
    version: int
    claim_id: str
    review_request_id: str
    recommendation_id: str
    readiness_assessment_id: str
    promotion_id: str
    organization_id: str
    environment_id: str
    classification: str
    assignment_policy_id: str
    assignment_policy_digest: str
    assignment_policy_version: str
    assignment_adapter_id: str
    assignment_receipt_digest: str
    requester_subject_digest: str
    browser_session_binding_digest: str
    source_review_request_digest: str
    source_binding_digest: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_assignments: tuple[tuple[str, str, str, str, str], ...]
    assignment_digest: str
    routing_digest: str
    eligibility_digest: str
    separation_digest: str
    artifact_digest: str
    manifest_digest: str
    state: str
    assigned_at: datetime
    expires_at: datetime
    purpose: str
    canonical_digest: str
    review_requested: bool = True
    reviewer_assigned: bool = True
    immutable_assignments_confirmed: bool = True
    encrypted_identity_references: bool = True
    transient_identity_buffers_erased: bool = True
    directory_channel_closed: bool = True
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
        tracks = tuple(item[0] for item in self.track_assignments)
        statuses = tuple(item[4] for item in self.track_assignments)
        reviewers = tuple(item[3] for item in self.track_assignments)
        if (
            self.version != 1
            or self.source_outcome not in {"preferred", "tie", "no_support"}
            or self.option_count < 1
            or self.preferred_count not in {0, 1}
            or (self.source_outcome == "preferred") != (self.preferred_count == 1)
            or tracks != (TECHNICAL_TRACK, SERVICE_IMPACT_TRACK)
            or statuses != (ASSIGNED, ASSIGNED)
            or len(set(reviewers)) != 2
            or self.state != "reviewers_assigned"
            or not _aware(self.assigned_at, self.expires_at)
            or self.expires_at <= self.assigned_at
            or not all(
                (
                    self.review_requested,
                    self.reviewer_assigned,
                    self.immutable_assignments_confirmed,
                    self.encrypted_identity_references,
                    self.transient_identity_buffers_erased,
                    self.directory_channel_closed,
                )
            )
            or any(
                (
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
            raise ValueError("invalid recommendation reviewer assignment record")


@dataclass(frozen=True, slots=True)
class RecommendationReviewerAssignmentManifest:
    assignment_set_id: str
    review_request_id: str
    recommendation_id: str
    track_assignments: tuple[tuple[str, str, str, str, str], ...]
    state: str
    assigned_at: datetime
    expires_at: datetime
    reviewer_assigned: bool


@dataclass(frozen=True, slots=True)
class RecommendationReviewerAssignmentResult:
    record: RecommendationReviewerAssignmentRecord
    manifest: RecommendationReviewerAssignmentManifest
