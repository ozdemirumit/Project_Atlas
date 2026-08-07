from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier
from atlas.modules.knowledge.domain.review_finding import OperationalKnowledgeReviewFindingItem

OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_PRESENTED = "operational_knowledge_review_finding_presented"
TRACKS = frozenset(("review-track.domain", "review-track.security"))
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge finding presentation identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeFindingPresentationPolicySnapshot:
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
            or self.required_assurance_level is not AssuranceLevel.HARDWARE_BACKED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(self.subject_digest_salt_digest, self.canonical_digest)
        ):
            raise ValueError("Operational knowledge finding presentation policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeFindingPresentationInstruction:
    finding_presentation_id: str
    organization_id: str
    environment_id: str
    source_finding_packet_id: str
    source_finding_digest: str
    source_finding_artifact_id: str
    source_lease_id: str
    source_lease_digest: str
    source_content_presentation_id: str
    source_content_presentation_digest: str
    source_assignment_set_id: str
    track_code: str
    lease_holder_subject_digest: str
    browser_session_binding_digest: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    draft_version_id: str
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
            self.source_content_presentation_id,
            self.source_assignment_set_id,
            self.track_code,
            self.source_draft_id,
            self.knowledge_item_id,
            self.draft_version_id,
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
                self.source_content_presentation_digest,
                self.lease_holder_subject_digest,
                self.browser_session_binding_digest,
                self.source_draft_digest,
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
            raise ValueError("Operational knowledge finding presentation instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeFindingPresentationReceipt:
    finding_presentation_id: str
    schema_version: str
    version: int
    presenter_id: str
    attested_by: str
    source_finding_packet_id: str
    source_finding_digest: str
    track_code: str
    media_type: str
    findings: tuple[OperationalKnowledgeReviewFindingItem, ...]
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
            raise ValueError("Operational knowledge finding presentation receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeFindingPresentationClaim:
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
            raise ValueError("Operational knowledge finding presentation claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeFindingPresentationRecord:
    finding_presentation_id: str
    schema_version: str
    version: int
    claim_id: str
    source_finding_packet_id: str
    source_finding_digest: str
    source_lease_id: str
    source_lease_digest: str
    source_content_presentation_id: str
    source_content_presentation_digest: str
    source_assignment_set_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    draft_version_id: str
    title: str
    classification: str
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
    instance_state: str
    purpose: str
    canonical_digest: str
    review_requested: bool = True
    reviewer_assigned: bool = True
    content_inspection_opened: bool = True
    content_disclosed: bool = True
    finding_recorded: bool = True
    finding_presented: bool = True
    domain_finding_recorded: bool = False
    security_finding_recorded: bool = False
    exact_assignee_verified: bool = True
    browser_session_bound: bool = True
    source_integrity_verified: bool = True
    encrypted_source_verified: bool = True
    transient_buffers_erased: bool = True
    artifact_channel_closed: bool = True
    domain_review_completed: bool = False
    security_review_completed: bool = False
    correction_created: bool = False
    knowledge_approved: bool = False
    knowledge_published: bool = False
    chunks_created: bool = False
    embeddings_created: bool = False
    retrieval_published: bool = False
    model_context_available: bool = False
    graph_updated: bool = False
    scheduled: bool = False
    workflow_continued: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.finding_presentation_id,
            self.schema_version,
            self.claim_id,
            self.source_finding_packet_id,
            self.source_lease_id,
            self.source_content_presentation_id,
            self.source_assignment_set_id,
            self.organization_id,
            self.environment_id,
            self.review_request_id,
            self.source_draft_id,
            self.knowledge_item_id,
            self.draft_version_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.track_code,
            self.presentation_policy_id,
            self.presentation_policy_version,
            self.presenter_id,
            self.instance_state,
        )
        later_authority = (
            self.domain_review_completed,
            self.security_review_completed,
            self.correction_created,
            self.knowledge_approved,
            self.knowledge_published,
            self.chunks_created,
            self.embeddings_created,
            self.retrieval_published,
            self.model_context_available,
            self.graph_updated,
            self.scheduled,
            self.workflow_continued,
            self.execution_authorized,
            self.deployment_approved,
            self.infrastructure_mutation_performed,
        )
        track_flag_valid = (
            self.track_code == "review-track.domain"
            and self.domain_finding_recorded
            and not self.security_finding_recorded
        ) or (
            self.track_code == "review-track.security"
            and self.security_finding_recorded
            and not self.domain_finding_recorded
        )
        if (
            self.version != 1
            or self.instance_state != OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_PRESENTED
            or self.track_code not in TRACKS
            or not track_flag_valid
            or not 1 <= len(self.title.strip()) <= 200
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
                    self.finding_recorded,
                    self.finding_presented,
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
                self.source_content_presentation_digest,
                self.source_draft_digest,
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
            raise ValueError("Operational knowledge finding presentation record is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeFindingPresentationGrant:
    record: OperationalKnowledgeFindingPresentationRecord
    findings: tuple[OperationalKnowledgeReviewFindingItem, ...]

    def __post_init__(self) -> None:
        if len(self.findings) != self.record.finding_count:
            raise ValueError("Operational knowledge finding presentation grant is invalid")
