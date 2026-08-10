from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
RECOMMENDATION_HUMAN_REVIEW_FINDING_RECORDED = "recommendation_human_review_finding_recorded"
TRACKS = frozenset(("review-track.technical", "review-track.service-impact"))


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "recommendation human review finding identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


def _bounded_text(value: str, minimum: int, maximum: int) -> bool:
    stripped = value.strip()
    return (
        minimum <= len(stripped) <= maximum
        and "\x00" not in stripped
        and all(character in "\n\r\t" or ord(character) >= 32 for character in stripped)
    )


@dataclass(frozen=True, slots=True)
class RecommendationHumanReviewFindingItem:
    category_code: str
    severity_code: str
    summary: str
    detail: str

    def __post_init__(self) -> None:
        _ids(self.category_code, self.severity_code)
        if not _bounded_text(self.summary, 10, 200) or not _bounded_text(self.detail, 20, 4000):
            raise ValueError("Recommendation human review finding item is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationHumanReviewFindingPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_source_schema: str
    required_source_state: str
    required_recorder_id: str
    required_recorder_attestor_id: str
    required_receipt_schema: str
    subject_digest_salt_digest: str
    finding_store_id: str
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
    maximum_authentication_age_minutes: int
    maximum_findings: int
    maximum_summary_characters: int
    maximum_detail_characters: int
    maximum_packet_bytes: int
    technical_category_codes: tuple[str, ...]
    service_impact_category_codes: tuple[str, ...]
    severity_codes: tuple[str, ...]
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
            self.required_recorder_id,
            self.required_recorder_attestor_id,
            self.required_receipt_schema,
            self.finding_store_id,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.signed_by,
            *self.technical_category_codes,
            *self.service_impact_category_codes,
            *self.severity_codes,
        )
        catalogs = (
            self.technical_category_codes,
            self.service_impact_category_codes,
            self.severity_codes,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_findings <= 20
            or not 10 <= self.maximum_summary_characters <= 200
            or not 20 <= self.maximum_detail_characters <= 4000
            or not 1024 <= self.maximum_packet_bytes <= 32768
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or any(not catalog or len(set(catalog)) != len(catalog) for catalog in catalogs)
            or self.required_assurance_level is not AssuranceLevel.HARDWARE_BACKED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(self.subject_digest_salt_digest, self.canonical_digest)
        ):
            raise ValueError("Recommendation human review finding policy is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationHumanReviewFindingInstruction:
    finding_packet_id: str
    organization_id: str
    environment_id: str
    source_lease_id: str
    source_lease_digest: str
    source_presentation_id: str
    source_presentation_digest: str
    source_assignment_set_id: str
    recommendation_id: str
    review_request_id: str
    readiness_assessment_id: str
    promotion_id: str
    recommendation_artifact_digest: str
    presented_content_digest: str
    track_code: str
    lease_holder_subject_digest: str
    browser_session_binding_digest: str
    classification: str
    finding_store_id: str
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
    finding_policy_digest: str
    purpose: str
    findings: tuple[RecommendationHumanReviewFindingItem, ...]
    maximum_packet_bytes: int
    expires_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.finding_packet_id,
            self.organization_id,
            self.environment_id,
            self.source_lease_id,
            self.source_presentation_id,
            self.source_assignment_set_id,
            self.recommendation_id,
            self.review_request_id,
            self.readiness_assessment_id,
            self.promotion_id,
            self.track_code,
            self.classification,
            self.finding_store_id,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
        )
        if (
            self.track_code not in TRACKS
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 1 <= len(self.findings) <= 20
            or not 1024 <= self.maximum_packet_bytes <= 32768
            or self.expires_at.tzinfo is None
            or not _digests(
                self.source_lease_digest,
                self.source_presentation_digest,
                self.recommendation_artifact_digest,
                self.presented_content_digest,
                self.lease_holder_subject_digest,
                self.browser_session_binding_digest,
                self.finding_policy_digest,
            )
        ):
            raise ValueError("Recommendation human review finding instruction is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationHumanReviewFindingReceipt:
    finding_packet_id: str
    schema_version: str
    version: int
    recorder_id: str
    attested_by: str
    source_presentation_id: str
    source_presentation_digest: str
    track_code: str
    finding_artifact_id: str
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
    cleanup_digest: str
    created_at: datetime
    expires_at: datetime
    immutable_finding_confirmed: bool
    encrypted_at_rest: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.finding_packet_id,
            self.schema_version,
            self.recorder_id,
            self.attested_by,
            self.source_presentation_id,
            self.track_code,
            self.finding_artifact_id,
        )
        if (
            self.version != 1
            or self.track_code not in TRACKS
            or not 1 <= self.finding_count <= 20
            or not 1 <= self.finding_bytes <= 32768
            or self.created_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.created_at < self.expires_at
            or not all(
                (
                    self.immutable_finding_confirmed,
                    self.encrypted_at_rest,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.source_presentation_digest,
                self.finding_content_digest,
                self.finding_metadata_digest,
                self.lineage_digest,
                self.category_catalog_digest,
                self.severity_catalog_digest,
                self.access_digest,
                self.retention_digest,
                self.encryption_digest,
                self.cleanup_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation human review finding receipt is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationHumanReviewFindingClaim:
    claim_id: str
    schema_version: str
    version: int
    source_presentation_id: str
    source_presentation_digest: str
    finding_packet_id: str
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
            self.source_presentation_id,
            self.finding_packet_id,
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
                self.source_presentation_digest,
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation human review finding claim is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationHumanReviewFindingRecord:
    finding_packet_id: str
    schema_version: str
    version: int
    claim_id: str
    source_lease_id: str
    source_lease_digest: str
    source_presentation_id: str
    source_presentation_digest: str
    source_assignment_set_id: str
    recommendation_id: str
    review_request_id: str
    readiness_assessment_id: str
    promotion_id: str
    recommendation_artifact_digest: str
    organization_id: str
    environment_id: str
    classification: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_code: str
    lease_holder_subject_digest: str
    browser_session_binding_digest: str
    presented_content_digest: str
    finding_artifact_id: str
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
    cleanup_digest: str
    finding_policy_id: str
    finding_policy_digest: str
    finding_policy_version: str
    recorder_id: str
    created_at: datetime
    expires_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    review_requested: bool = True
    reviewer_assigned: bool = True
    content_inspection_opened: bool = True
    content_disclosed: bool = True
    human_findings_recorded: bool = True
    technical_finding_recorded: bool = False
    service_impact_finding_recorded: bool = False
    exact_assignee_verified: bool = True
    browser_session_bound: bool = True
    source_integrity_verified: bool = True
    immutable_finding_confirmed: bool = True
    encrypted_at_rest: bool = True
    transient_buffers_erased: bool = True
    artifact_channel_closed: bool = True
    human_review_completed: bool = False
    recommendation_approved: bool = False
    correction_created: bool = False
    workflow_created: bool = False
    itsm_record_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.finding_packet_id,
            self.schema_version,
            self.claim_id,
            self.source_lease_id,
            self.source_presentation_id,
            self.source_assignment_set_id,
            self.recommendation_id,
            self.review_request_id,
            self.readiness_assessment_id,
            self.promotion_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.track_code,
            self.finding_artifact_id,
            self.finding_policy_id,
            self.finding_policy_version,
            self.recorder_id,
            self.state,
        )
        later_authority = (
            self.human_review_completed,
            self.recommendation_approved,
            self.correction_created,
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
        ) or (
            self.track_code == "review-track.service-impact"
            and self.service_impact_finding_recorded
            and not self.technical_finding_recorded
        )
        if (
            self.version != 1
            or self.state != RECOMMENDATION_HUMAN_REVIEW_FINDING_RECORDED
            or self.track_code not in TRACKS
            or not track_flag_valid
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 1 <= self.finding_count <= 20
            or not 1 <= self.finding_bytes <= 32768
            or not 1 <= self.option_count <= 5
            or not 0 <= self.preferred_count <= self.option_count
            or self.created_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.created_at < self.expires_at
            or not all(
                (
                    self.review_requested,
                    self.reviewer_assigned,
                    self.content_inspection_opened,
                    self.content_disclosed,
                    self.human_findings_recorded,
                    self.exact_assignee_verified,
                    self.browser_session_bound,
                    self.source_integrity_verified,
                    self.immutable_finding_confirmed,
                    self.encrypted_at_rest,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                )
            )
            or any(later_authority)
            or not _digests(
                self.source_lease_digest,
                self.source_presentation_digest,
                self.recommendation_artifact_digest,
                self.lease_holder_subject_digest,
                self.browser_session_binding_digest,
                self.presented_content_digest,
                self.finding_content_digest,
                self.finding_metadata_digest,
                self.lineage_digest,
                self.category_catalog_digest,
                self.severity_catalog_digest,
                self.access_digest,
                self.retention_digest,
                self.encryption_digest,
                self.cleanup_digest,
                self.finding_policy_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation human review finding record is invalid")
