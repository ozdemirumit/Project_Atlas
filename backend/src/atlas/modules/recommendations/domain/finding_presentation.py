from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier
from atlas.modules.recommendations.domain.human_review_finding import (
    RecommendationHumanReviewFindingItem,
)

RECOMMENDATION_HUMAN_REVIEW_FINDING_PRESENTED = "recommendation_human_review_finding_presented"
TRACKS = frozenset(("review-track.technical", "review-track.service-impact"))
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "recommendation finding presentation identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class RecommendationFindingPresentationPolicySnapshot:
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
    maximum_authentication_age_minutes: int
    maximum_findings: int
    maximum_packet_bytes: int
    permitted_media_type: str
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
            self.permitted_media_type,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 1 <= self.maximum_findings <= 20
            or not 1024 <= self.maximum_packet_bytes <= 32768
            or self.permitted_media_type != "media-type.application-json"
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
            raise ValueError("Recommendation finding presentation policy is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationFindingPresentationInstruction:
    finding_presentation_id: str
    organization_id: str
    environment_id: str
    source_finding_packet_id: str
    source_finding_digest: str
    source_finding_artifact_id: str
    source_lease_id: str
    source_lease_digest: str
    source_presentation_id: str
    source_presentation_digest: str
    source_assignment_set_id: str
    track_code: str
    lease_holder_subject_digest: str
    browser_session_binding_digest: str
    recommendation_id: str
    review_request_id: str
    readiness_assessment_id: str
    promotion_id: str
    recommendation_artifact_digest: str
    presented_content_digest: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
    expected_finding_count: int
    expected_finding_bytes: int
    expected_content_digest: str
    expected_metadata_digest: str
    expected_lineage_digest: str
    expected_category_catalog_digest: str
    expected_severity_catalog_digest: str
    expected_access_digest: str
    expected_retention_digest: str
    expected_encryption_digest: str
    expected_source_cleanup_digest: str
    presentation_policy_digest: str
    purpose: str
    maximum_findings: int
    maximum_packet_bytes: int
    expires_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.finding_presentation_id,
            self.organization_id,
            self.environment_id,
            self.source_finding_packet_id,
            self.source_finding_artifact_id,
            self.source_lease_id,
            self.source_presentation_id,
            self.source_assignment_set_id,
            self.track_code,
            self.recommendation_id,
            self.review_request_id,
            self.readiness_assessment_id,
            self.promotion_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
        )
        if (
            self.track_code not in TRACKS
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 1 <= self.expected_finding_count <= self.maximum_findings <= 20
            or not 1 <= self.expected_finding_bytes <= self.maximum_packet_bytes <= 32768
            or self.expires_at.tzinfo is None
            or not _digests(
                self.source_finding_digest,
                self.source_lease_digest,
                self.source_presentation_digest,
                self.lease_holder_subject_digest,
                self.browser_session_binding_digest,
                self.recommendation_artifact_digest,
                self.presented_content_digest,
                self.expected_content_digest,
                self.expected_metadata_digest,
                self.expected_lineage_digest,
                self.expected_category_catalog_digest,
                self.expected_severity_catalog_digest,
                self.expected_access_digest,
                self.expected_retention_digest,
                self.expected_encryption_digest,
                self.expected_source_cleanup_digest,
                self.presentation_policy_digest,
            )
        ):
            raise ValueError("Recommendation finding presentation instruction is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationFindingPresentationReceipt:
    finding_presentation_id: str
    schema_version: str
    version: int
    presenter_id: str
    attested_by: str
    source_finding_packet_id: str
    source_finding_digest: str
    track_code: str
    media_type: str
    findings: tuple[RecommendationHumanReviewFindingItem, ...]
    finding_count: int
    finding_bytes: int
    finding_content_digest: str
    finding_metadata_digest: str
    lineage_digest: str
    category_catalog_digest: str
    severity_catalog_digest: str
    access_digest: str
    retention_digest: str
    encryption_digest: str
    source_cleanup_digest: str
    presentation_cleanup_digest: str
    presented_at: datetime
    expires_at: datetime
    source_integrity_verified: bool
    encrypted_source_verified: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.finding_presentation_id,
            self.schema_version,
            self.presenter_id,
            self.attested_by,
            self.source_finding_packet_id,
            self.track_code,
            self.media_type,
        )
        if (
            self.version != 1
            or self.track_code not in TRACKS
            or self.media_type != "media-type.application-json"
            or len(self.findings) != self.finding_count
            or not 1 <= self.finding_count <= 20
            or not 1 <= self.finding_bytes <= 32768
            or self.presented_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.presented_at < self.expires_at
            or not all(
                (
                    self.source_integrity_verified,
                    self.encrypted_source_verified,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.source_finding_digest,
                self.finding_content_digest,
                self.finding_metadata_digest,
                self.lineage_digest,
                self.category_catalog_digest,
                self.severity_catalog_digest,
                self.access_digest,
                self.retention_digest,
                self.encryption_digest,
                self.source_cleanup_digest,
                self.presentation_cleanup_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation finding presentation receipt is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationFindingPresentationClaim:
    claim_id: str
    schema_version: str
    version: int
    source_finding_packet_id: str
    source_finding_digest: str
    finding_presentation_id: str
    organization_id: str
    environment_id: str
    track_code: str
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
            self.source_finding_packet_id,
            self.finding_presentation_id,
            self.organization_id,
            self.environment_id,
            self.track_code,
        )
        if (
            self.version != 1
            or self.track_code not in TRACKS
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_finding_digest,
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation finding presentation claim is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationFindingPresentationRecord:
    finding_presentation_id: str
    schema_version: str
    version: int
    claim_id: str
    source_finding_packet_id: str
    source_finding_digest: str
    source_lease_id: str
    source_lease_digest: str
    source_presentation_id: str
    source_presentation_digest: str
    source_assignment_set_id: str
    recommendation_id: str
    readiness_assessment_id: str
    promotion_id: str
    recommendation_artifact_digest: str
    presented_content_digest: str
    organization_id: str
    environment_id: str
    review_request_id: str
    classification: str
    source_outcome: str
    option_count: int
    preferred_count: int
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
    track_code: str
    lease_holder_subject_digest: str
    browser_session_binding_digest: str
    finding_count: int
    finding_bytes: int
    finding_content_digest: str
    finding_metadata_digest: str
    lineage_digest: str
    category_catalog_digest: str
    severity_catalog_digest: str
    access_digest: str
    retention_digest: str
    encryption_digest: str
    source_cleanup_digest: str
    presentation_cleanup_digest: str
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
    human_findings_recorded: bool = True
    human_findings_presented: bool = True
    technical_finding_recorded: bool = False
    service_impact_finding_recorded: bool = False
    technical_findings_presented: bool = False
    service_impact_findings_presented: bool = False
    exact_assignee_verified: bool = True
    browser_session_bound: bool = True
    source_integrity_verified: bool = True
    encrypted_source_verified: bool = True
    transient_buffers_erased: bool = True
    artifact_channel_closed: bool = True
    human_review_completed: bool = False
    correction_created: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    itsm_record_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.finding_presentation_id,
            self.schema_version,
            self.claim_id,
            self.source_finding_packet_id,
            self.source_lease_id,
            self.source_presentation_id,
            self.source_assignment_set_id,
            self.recommendation_id,
            self.readiness_assessment_id,
            self.promotion_id,
            self.organization_id,
            self.environment_id,
            self.review_request_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.track_code,
            self.presentation_policy_id,
            self.presentation_policy_version,
            self.presenter_id,
            self.state,
        )
        later_authority = (
            self.human_review_completed,
            self.correction_created,
            self.recommendation_approved,
            self.workflow_created,
            self.itsm_record_created,
            self.execution_authorized,
            self.deployment_authorized,
            self.infrastructure_mutated,
        )
        track_flag_valid = (
            self.track_code == "review-track.technical"
            and self.technical_finding_recorded
            and not self.service_impact_finding_recorded
            and self.technical_findings_presented
            and not self.service_impact_findings_presented
        ) or (
            self.track_code == "review-track.service-impact"
            and self.service_impact_finding_recorded
            and not self.technical_finding_recorded
            and self.service_impact_findings_presented
            and not self.technical_findings_presented
        )
        if (
            self.version != 1
            or self.state != RECOMMENDATION_HUMAN_REVIEW_FINDING_PRESENTED
            or self.track_code not in TRACKS
            or not track_flag_valid
            or self.source_outcome not in {"preferred", "tie", "no_support"}
            or not 1 <= self.option_count <= 5
            or not 0 <= self.preferred_count <= self.option_count
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 1 <= self.finding_count <= 20
            or not 1 <= self.finding_bytes <= 32768
            or self.presented_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.presented_at < self.expires_at
            or not all(
                (
                    self.review_requested,
                    self.reviewer_assigned,
                    self.content_inspection_opened,
                    self.content_disclosed,
                    self.human_findings_recorded,
                    self.human_findings_presented,
                    self.exact_assignee_verified,
                    self.browser_session_bound,
                    self.source_integrity_verified,
                    self.encrypted_source_verified,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                )
            )
            or any(later_authority)
            or not _digests(
                self.source_finding_digest,
                self.source_lease_digest,
                self.source_presentation_digest,
                self.recommendation_artifact_digest,
                self.presented_content_digest,
                self.lease_holder_subject_digest,
                self.browser_session_binding_digest,
                self.finding_content_digest,
                self.finding_metadata_digest,
                self.lineage_digest,
                self.category_catalog_digest,
                self.severity_catalog_digest,
                self.access_digest,
                self.retention_digest,
                self.encryption_digest,
                self.source_cleanup_digest,
                self.presentation_cleanup_digest,
                self.presentation_policy_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation finding presentation record is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationFindingPresentationGrant:
    record: RecommendationFindingPresentationRecord
    findings: tuple[RecommendationHumanReviewFindingItem, ...]

    def __post_init__(self) -> None:
        if len(self.findings) != self.record.finding_count:
            raise ValueError("Recommendation finding presentation grant is invalid")
