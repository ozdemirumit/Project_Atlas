from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_RECORDED = "operational_knowledge_review_finding_recorded"
TRACKS = frozenset(("review-track.domain", "review-track.security"))


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge review finding identifier")


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
class OperationalKnowledgeReviewFindingItem:
    category_code: str
    severity_code: str
    summary: str
    detail: str

    def __post_init__(self) -> None:
        _ids(self.category_code, self.severity_code)
        if not _bounded_text(self.summary, 10, 200) or not _bounded_text(self.detail, 20, 4000):
            raise ValueError("Operational knowledge review finding item is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewFindingPolicySnapshot:
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
    maximum_authentication_age_minutes: int
    maximum_findings: int
    maximum_summary_characters: int
    maximum_detail_characters: int
    maximum_packet_bytes: int
    domain_category_codes: tuple[str, ...]
    security_category_codes: tuple[str, ...]
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
            self.signed_by,
            *self.domain_category_codes,
            *self.security_category_codes,
            *self.severity_codes,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_findings <= 20
            or not 10 <= self.maximum_summary_characters <= 200
            or not 20 <= self.maximum_detail_characters <= 4000
            or not 1024 <= self.maximum_packet_bytes <= 32768
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not self.domain_category_codes
            or not self.security_category_codes
            or not self.severity_codes
            or len(set(self.domain_category_codes)) != len(self.domain_category_codes)
            or len(set(self.security_category_codes)) != len(self.security_category_codes)
            or len(set(self.severity_codes)) != len(self.severity_codes)
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
            raise ValueError("Operational knowledge review finding policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewFindingInstruction:
    finding_packet_id: str
    organization_id: str
    environment_id: str
    source_lease_id: str
    source_lease_digest: str
    source_presentation_id: str
    source_presentation_digest: str
    source_assignment_set_id: str
    track_code: str
    lease_holder_subject_digest: str
    browser_session_binding_digest: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    draft_version_id: str
    presented_content_digest: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
    finding_policy_digest: str
    purpose: str
    findings: tuple[OperationalKnowledgeReviewFindingItem, ...]
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
            or not 1 <= len(self.findings) <= 20
            or not 1024 <= self.maximum_packet_bytes <= 32768
            or self.expires_at.tzinfo is None
            or not _digests(
                self.source_lease_digest,
                self.source_presentation_digest,
                self.lease_holder_subject_digest,
                self.browser_session_binding_digest,
                self.source_draft_digest,
                self.presented_content_digest,
                self.finding_policy_digest,
            )
        ):
            raise ValueError("Operational knowledge review finding instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewFindingReceipt:
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
            raise ValueError("Operational knowledge review finding receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewFindingClaim:
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
            raise ValueError("Operational knowledge review finding claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewFindingRecord:
    finding_packet_id: str
    schema_version: str
    version: int
    claim_id: str
    source_lease_id: str
    source_lease_digest: str
    source_presentation_id: str
    source_presentation_digest: str
    source_assignment_set_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    draft_version_id: str
    source_ingestion_id: str
    source_invocation_id: str
    connector_id: str
    instance_id: str
    capability_id: str
    title: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
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
    instance_state: str
    purpose: str
    canonical_digest: str
    review_requested: bool = True
    reviewer_assigned: bool = True
    content_inspection_opened: bool = True
    content_disclosed: bool = True
    finding_recorded: bool = True
    domain_finding_recorded: bool = False
    security_finding_recorded: bool = False
    exact_assignee_verified: bool = True
    browser_session_bound: bool = True
    source_integrity_verified: bool = True
    immutable_finding_confirmed: bool = True
    encrypted_at_rest: bool = True
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
            self.finding_packet_id,
            self.schema_version,
            self.claim_id,
            self.source_lease_id,
            self.source_presentation_id,
            self.source_assignment_set_id,
            self.organization_id,
            self.environment_id,
            self.review_request_id,
            self.source_draft_id,
            self.knowledge_item_id,
            self.draft_version_id,
            self.source_ingestion_id,
            self.source_invocation_id,
            self.connector_id,
            self.instance_id,
            self.capability_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.track_code,
            self.finding_artifact_id,
            self.finding_policy_id,
            self.finding_policy_version,
            self.recorder_id,
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
            or self.instance_state != OPERATIONAL_KNOWLEDGE_REVIEW_FINDING_RECORDED
            or self.track_code not in TRACKS
            or not track_flag_valid
            or not 1 <= len(self.title.strip()) <= 200
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 1 <= self.finding_count <= 20
            or not 1 <= self.finding_bytes <= 32768
            or self.created_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.created_at < self.expires_at
            or not all(
                (
                    self.review_requested,
                    self.reviewer_assigned,
                    self.content_inspection_opened,
                    self.content_disclosed,
                    self.finding_recorded,
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
                self.source_draft_digest,
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
            raise ValueError("Operational knowledge review finding record is invalid")
