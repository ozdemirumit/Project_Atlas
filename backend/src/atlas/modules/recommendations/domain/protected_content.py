from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from atlas.modules.ai.domain.protected_recommendation_presentation import (
    PresentedRecommendationOption,
)
from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier
from atlas.modules.recommendations.domain.protected_inspection import TRACKS

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
RECOMMENDATION_PROTECTED_CONTENT_PRESENTED = "recommendation_protected_content_presented"


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "recommendation protected content identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class RecommendationProtectedContentPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_source_schema: str
    required_source_state: str
    required_presenter_id: str
    required_presenter_attestor_id: str
    required_receipt_schema: str
    subject_digest_salt_digest: str
    output_media_type: str
    language: str
    redaction_profile_id: str
    maximum_authentication_age_minutes: int
    maximum_content_bytes: int
    require_exact_replay: bool
    require_plain_text: bool
    required_assurance_level: AssuranceLevel
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.required_source_schema,
            self.required_source_state,
            self.required_presenter_id,
            self.required_presenter_attestor_id,
            self.required_receipt_schema,
            self.output_media_type,
            self.language,
            self.redaction_profile_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 256 <= self.maximum_content_bytes <= 262_144
            or not self.require_exact_replay
            or not self.require_plain_text
            or self.output_media_type != "media-type.text-plain"
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(self.subject_digest_salt_digest, self.canonical_digest)
        ):
            raise ValueError("Recommendation protected content policy is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedContentInstruction:
    presentation_id: str
    organization_id: str
    environment_id: str
    lease_id: str
    lease_digest: str
    assignment_set_id: str
    track_code: str
    opaque_assignment_id: str
    lease_holder_subject_digest: str
    browser_session_binding_digest: str
    recommendation_id: str
    promotion_id: str
    recommendation_artifact_digest: str
    source_binding_digest: str
    classification: str
    outcome: str
    headline: str
    safety_notice: str
    options: tuple[PresentedRecommendationOption, ...]
    evidence_needs: tuple[str, ...]
    output_media_type: str
    language: str
    redaction_profile_id: str
    maximum_content_bytes: int
    presentation_policy_digest: str
    expires_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.presentation_id,
            self.organization_id,
            self.environment_id,
            self.lease_id,
            self.assignment_set_id,
            self.track_code,
            self.opaque_assignment_id,
            self.recommendation_id,
            self.promotion_id,
            self.classification,
            self.output_media_type,
            self.language,
            self.redaction_profile_id,
        )
        if (
            self.track_code not in TRACKS
            or self.outcome not in {"preferred", "tie", "no_support"}
            or not self.options
            or not self.headline.strip()
            or not self.safety_notice.strip()
            or not 256 <= self.maximum_content_bytes <= 262_144
            or self.expires_at.tzinfo is None
            or not _digests(
                self.lease_digest,
                self.lease_holder_subject_digest,
                self.browser_session_binding_digest,
                self.recommendation_artifact_digest,
                self.source_binding_digest,
                self.presentation_policy_digest,
            )
        ):
            raise ValueError("Recommendation protected content instruction is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedContentReceipt:
    presentation_id: str
    schema_version: str
    version: int
    presenter_id: str
    attested_by: str
    lease_id: str
    lease_digest: str
    recommendation_id: str
    promotion_id: str
    recommendation_artifact_digest: str
    track_code: str
    lease_holder_subject_digest: str
    browser_session_binding_digest: str
    output_media_type: str
    language: str
    presented_content_digest: str
    content_bytes: int
    source_binding_digest: str
    redaction_digest: str
    truncation_digest: str
    cleanup_digest: str
    presented_at: datetime
    expires_at: datetime
    source_integrity_verified: bool
    redaction_applied: bool
    truncated: bool
    active_content_rejected: bool
    transient_buffers_erased: bool
    presenter_channel_closed: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.presentation_id,
            self.schema_version,
            self.presenter_id,
            self.attested_by,
            self.lease_id,
            self.recommendation_id,
            self.promotion_id,
            self.track_code,
            self.output_media_type,
            self.language,
        )
        if (
            self.version != 1
            or self.track_code not in TRACKS
            or not 1 <= self.content_bytes <= 262_144
            or self.presented_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.presented_at < self.expires_at
            or not all(
                (
                    self.source_integrity_verified,
                    self.redaction_applied,
                    self.active_content_rejected,
                    self.transient_buffers_erased,
                    self.presenter_channel_closed,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.lease_digest,
                self.recommendation_artifact_digest,
                self.lease_holder_subject_digest,
                self.browser_session_binding_digest,
                self.presented_content_digest,
                self.source_binding_digest,
                self.redaction_digest,
                self.truncation_digest,
                self.cleanup_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation protected content receipt is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedContentClaim:
    claim_id: str
    schema_version: str
    version: int
    source_lease_id: str
    source_lease_digest: str
    presentation_id: str
    organization_id: str
    environment_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    purpose: str
    claimed_at: datetime
    request_binding_digest: str
    idempotency_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.source_lease_id,
            self.presentation_id,
            self.organization_id,
            self.environment_id,
        )
        if (
            self.version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_lease_digest,
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation protected content claim is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedContentRecord:
    presentation_id: str
    schema_version: str
    version: int
    claim_id: str
    source_lease_id: str
    source_lease_digest: str
    source_assignment_set_id: str
    recommendation_id: str
    review_request_id: str
    readiness_assessment_id: str
    promotion_id: str
    organization_id: str
    environment_id: str
    classification: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_code: str
    opaque_assignment_id: str
    lease_holder_subject_digest: str
    browser_session_binding_digest: str
    recommendation_artifact_digest: str
    source_binding_digest: str
    output_media_type: str
    language: str
    presented_content_digest: str
    protected_content_bytes_returned: int
    redaction_digest: str
    truncation_digest: str
    cleanup_digest: str
    presentation_policy_id: str
    presentation_policy_digest: str
    presentation_policy_version: str
    presenter_id: str
    presented_at: datetime
    expires_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    review_requested: bool = True
    reviewer_assigned: bool = True
    content_inspection_opened: bool = True
    content_disclosed: bool = True
    exact_assignee_verified: bool = True
    browser_session_bound: bool = True
    source_integrity_verified: bool = True
    redaction_applied: bool = True
    truncated: bool = False
    active_content_rejected: bool = True
    transient_buffers_erased: bool = True
    presenter_channel_closed: bool = True
    human_findings_recorded: bool = False
    human_review_completed: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    itsm_record_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.presentation_id,
            self.schema_version,
            self.claim_id,
            self.source_lease_id,
            self.source_assignment_set_id,
            self.recommendation_id,
            self.review_request_id,
            self.readiness_assessment_id,
            self.promotion_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.track_code,
            self.opaque_assignment_id,
            self.output_media_type,
            self.language,
            self.presentation_policy_id,
            self.presentation_policy_version,
            self.presenter_id,
            self.state,
        )
        later_authority = (
            self.human_findings_recorded,
            self.human_review_completed,
            self.recommendation_approved,
            self.workflow_created,
            self.itsm_record_created,
            self.execution_authorized,
            self.deployment_authorized,
            self.infrastructure_mutated,
        )
        if (
            self.version != 1
            or self.state != RECOMMENDATION_PROTECTED_CONTENT_PRESENTED
            or self.track_code not in TRACKS
            or self.source_outcome not in {"preferred", "tie", "no_support"}
            or self.option_count < 1
            or self.preferred_count not in {0, 1}
            or (self.source_outcome == "preferred") != (self.preferred_count == 1)
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 1 <= self.protected_content_bytes_returned <= 262_144
            or self.presented_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.presented_at < self.expires_at
            or not all(
                (
                    self.review_requested,
                    self.reviewer_assigned,
                    self.content_inspection_opened,
                    self.content_disclosed,
                    self.exact_assignee_verified,
                    self.browser_session_bound,
                    self.source_integrity_verified,
                    self.redaction_applied,
                    self.active_content_rejected,
                    self.transient_buffers_erased,
                    self.presenter_channel_closed,
                )
            )
            or any(later_authority)
            or not _digests(
                self.source_lease_digest,
                self.lease_holder_subject_digest,
                self.browser_session_binding_digest,
                self.recommendation_artifact_digest,
                self.source_binding_digest,
                self.presented_content_digest,
                self.redaction_digest,
                self.truncation_digest,
                self.cleanup_digest,
                self.presentation_policy_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation protected content record is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedContentGrant:
    record: RecommendationProtectedContentRecord
    content: str = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            not self.content
            or len(self.content.encode("utf-8")) != self.record.protected_content_bytes_returned
        ):
            raise ValueError("Recommendation protected content grant is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedContentPresenterGrant:
    receipt: RecommendationProtectedContentReceipt
    content: str = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.content or len(self.content.encode("utf-8")) != self.receipt.content_bytes:
            raise ValueError("Recommendation protected presenter grant is invalid")
