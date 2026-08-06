from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
OPERATIONAL_KNOWLEDGE_REVIEWERS_ASSIGNED = "operational_knowledge_reviewers_assigned"
ASSIGNED = "assigned"


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge reviewer assignment identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewerAssignmentPolicySnapshot:
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
    directory_source_id: str
    directory_source_digest: str
    domain_eligibility_profile_id: str
    domain_eligibility_profile_digest: str
    security_eligibility_profile_id: str
    security_eligibility_profile_digest: str
    subject_digest_salt_id: str
    subject_digest_salt_digest: str
    maximum_source_age_minutes: int
    assignment_ttl_minutes: int
    require_distinct_reviewers: bool
    require_upstream_actor_exclusion: bool
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
            self.required_adapter_id,
            self.required_adapter_attestor_id,
            self.required_receipt_schema,
            self.directory_source_id,
            self.domain_eligibility_profile_id,
            self.security_eligibility_profile_id,
            self.subject_digest_salt_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_source_age_minutes <= 1440
            or not 5 <= self.assignment_ttl_minutes <= 10_080
            or not self.require_distinct_reviewers
            or not self.require_upstream_actor_exclusion
            or self.required_assurance_level is not AssuranceLevel.HARDWARE_BACKED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(
                self.directory_source_digest,
                self.domain_eligibility_profile_digest,
                self.security_eligibility_profile_digest,
                self.subject_digest_salt_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge reviewer assignment policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewerAssignmentInstruction:
    assignment_set_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    manifest_id: str
    manifest_digest: str
    routing_digest: str
    governance_digest: str
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    domain_status: str
    security_status: str
    directory_source_id: str
    directory_source_digest: str
    domain_eligibility_profile_id: str
    domain_eligibility_profile_digest: str
    security_eligibility_profile_id: str
    security_eligibility_profile_digest: str
    subject_digest_salt_id: str
    subject_digest_salt_digest: str
    exclusion_subject_digests: tuple[str, ...]
    assignment_ttl_minutes: int
    assignment_policy_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.assignment_set_id,
            self.organization_id,
            self.environment_id,
            self.review_request_id,
            self.source_draft_id,
            self.knowledge_item_id,
            self.manifest_id,
            self.domain_track_code,
            self.security_track_code,
            self.domain_queue_id,
            self.security_queue_id,
            self.domain_status,
            self.security_status,
            self.directory_source_id,
            self.domain_eligibility_profile_id,
            self.security_eligibility_profile_id,
            self.subject_digest_salt_id,
        )
        if (
            self.domain_track_code != "review-track.domain"
            or self.security_track_code != "review-track.security"
            or self.domain_status != "awaiting_reviewer"
            or self.security_status != "awaiting_reviewer"
            or self.domain_queue_id == self.security_queue_id
            or not 2 <= len(self.exclusion_subject_digests) <= 64
            or len(set(self.exclusion_subject_digests)) != len(self.exclusion_subject_digests)
            or not 5 <= self.assignment_ttl_minutes <= 10_080
            or not _digests(
                self.review_request_digest,
                self.source_draft_digest,
                self.manifest_digest,
                self.routing_digest,
                self.governance_digest,
                self.directory_source_digest,
                self.domain_eligibility_profile_digest,
                self.security_eligibility_profile_digest,
                self.subject_digest_salt_digest,
                *self.exclusion_subject_digests,
                self.assignment_policy_digest,
            )
        ):
            raise ValueError("Operational knowledge reviewer assignment instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewerAssignmentReceipt:
    assignment_set_id: str
    schema_version: str
    version: int
    adapter_id: str
    attested_by: str
    review_request_id: str
    review_request_digest: str
    manifest_id: str
    manifest_digest: str
    domain_assignment_id: str
    security_assignment_id: str
    domain_reviewer_subject_digest: str
    security_reviewer_subject_digest: str
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    domain_status: str
    security_status: str
    assignment_digest: str
    routing_digest: str
    eligibility_digest: str
    separation_digest: str
    artifact_digest: str
    created_at: datetime
    expires_at: datetime
    directory_snapshot_current: bool
    eligibility_verified: bool
    upstream_actors_excluded: bool
    distinct_reviewers_verified: bool
    immutable_assignments_confirmed: bool
    encrypted_identity_references: bool
    transient_identity_buffers_erased: bool
    directory_channel_closed: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.assignment_set_id,
            self.schema_version,
            self.adapter_id,
            self.attested_by,
            self.review_request_id,
            self.manifest_id,
            self.domain_assignment_id,
            self.security_assignment_id,
            self.domain_track_code,
            self.security_track_code,
            self.domain_queue_id,
            self.security_queue_id,
            self.domain_status,
            self.security_status,
        )
        if (
            self.version != 1
            or self.domain_assignment_id == self.security_assignment_id
            or self.domain_reviewer_subject_digest == self.security_reviewer_subject_digest
            or self.domain_status != ASSIGNED
            or self.security_status != ASSIGNED
            or self.created_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.created_at
            or not all(
                (
                    self.directory_snapshot_current,
                    self.eligibility_verified,
                    self.upstream_actors_excluded,
                    self.distinct_reviewers_verified,
                    self.immutable_assignments_confirmed,
                    self.encrypted_identity_references,
                    self.transient_identity_buffers_erased,
                    self.directory_channel_closed,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.review_request_digest,
                self.manifest_digest,
                self.domain_reviewer_subject_digest,
                self.security_reviewer_subject_digest,
                self.assignment_digest,
                self.routing_digest,
                self.eligibility_digest,
                self.separation_digest,
                self.artifact_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge reviewer assignment receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewerAssignmentClaim:
    claim_id: str
    schema_version: str
    version: int
    source_review_request_id: str
    source_review_request_digest: str
    assignment_set_id: str
    organization_id: str
    environment_id: str
    claimed_by: str
    purpose: str
    claimed_at: datetime
    request_binding_digest: str
    idempotency_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.source_review_request_id,
            self.assignment_set_id,
            self.organization_id,
            self.environment_id,
            self.claimed_by,
        )
        if (
            self.version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_review_request_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge reviewer assignment claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewerAssignmentRecord:
    assignment_set_id: str
    schema_version: str
    version: int
    claim_id: str
    source_review_request_id: str
    source_review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    organization_id: str
    environment_id: str
    knowledge_item_id: str
    draft_version_id: str
    source_ingestion_id: str
    source_invocation_id: str
    connector_id: str
    instance_id: str
    capability_id: str
    title: str
    knowledge_lifecycle: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    encryption_profile_id: str
    manifest_id: str
    manifest_digest: str
    domain_assignment_id: str
    security_assignment_id: str
    domain_reviewer_subject_digest: str
    security_reviewer_subject_digest: str
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    domain_status: str
    security_status: str
    assignment_digest: str
    routing_digest: str
    eligibility_digest: str
    separation_digest: str
    artifact_digest: str
    assignment_policy_id: str
    assignment_policy_digest: str
    assignment_policy_version: str
    assignment_adapter_id: str
    created_at: datetime
    expires_at: datetime
    instance_state: str
    requested_by: str
    purpose: str
    canonical_digest: str
    review_requested: bool = True
    reviewer_assigned: bool = True
    immutable_assignments_confirmed: bool = True
    encrypted_identity_references: bool = True
    transient_identity_buffers_erased: bool = True
    directory_channel_closed: bool = True
    content_inspection_opened: bool = False
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
            self.assignment_set_id,
            self.schema_version,
            self.claim_id,
            self.source_review_request_id,
            self.source_draft_id,
            self.organization_id,
            self.environment_id,
            self.knowledge_item_id,
            self.draft_version_id,
            self.source_ingestion_id,
            self.source_invocation_id,
            self.connector_id,
            self.instance_id,
            self.capability_id,
            self.knowledge_lifecycle,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.manifest_id,
            self.domain_assignment_id,
            self.security_assignment_id,
            self.domain_track_code,
            self.security_track_code,
            self.domain_queue_id,
            self.security_queue_id,
            self.domain_status,
            self.security_status,
            self.assignment_policy_id,
            self.assignment_policy_version,
            self.assignment_adapter_id,
            self.instance_state,
            self.requested_by,
        )
        later_authority = (
            self.content_inspection_opened,
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
        if (
            self.version != 1
            or self.instance_state != OPERATIONAL_KNOWLEDGE_REVIEWERS_ASSIGNED
            or self.knowledge_lifecycle != "reviewer_assigned"
            or self.domain_status != ASSIGNED
            or self.security_status != ASSIGNED
            or self.domain_assignment_id == self.security_assignment_id
            or self.domain_reviewer_subject_digest == self.security_reviewer_subject_digest
            or not 1 <= len(self.title.strip()) <= 200
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.created_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.created_at
            or not _digests(
                self.source_review_request_digest,
                self.source_draft_digest,
                self.manifest_digest,
                self.domain_reviewer_subject_digest,
                self.security_reviewer_subject_digest,
                self.assignment_digest,
                self.routing_digest,
                self.eligibility_digest,
                self.separation_digest,
                self.artifact_digest,
                self.assignment_policy_digest,
                self.canonical_digest,
            )
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
            or any(later_authority)
        ):
            raise ValueError("Operational knowledge reviewer assignment record is invalid")
