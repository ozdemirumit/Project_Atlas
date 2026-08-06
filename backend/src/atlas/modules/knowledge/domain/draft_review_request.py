from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED = "operational_knowledge_review_requested"
AWAITING_REVIEWER = "awaiting_reviewer"


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge review request identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewRequestPolicySnapshot:
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
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    assignment_strategy: str
    sla_class: str
    maximum_source_age_minutes: int
    maximum_manifest_bytes: int
    require_classification_inheritance: bool
    require_access_policy_inheritance: bool
    require_retention_policy_inheritance: bool
    require_encryption_profile_inheritance: bool
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
            self.domain_track_code,
            self.security_track_code,
            self.domain_queue_id,
            self.security_queue_id,
            self.assignment_strategy,
            self.sla_class,
            self.signed_by,
        )
        if (
            self.version != 1
            or self.domain_track_code != "review-track.domain"
            or self.security_track_code != "review-track.security"
            or self.domain_queue_id == self.security_queue_id
            or not 1 <= self.maximum_source_age_minutes <= 1440
            or not 1 <= self.maximum_manifest_bytes <= 262_144
            or self.required_assurance_level is not AssuranceLevel.HARDWARE_BACKED
            or not all(
                (
                    self.require_classification_inheritance,
                    self.require_access_policy_inheritance,
                    self.require_retention_policy_inheritance,
                    self.require_encryption_profile_inheritance,
                    self.signature_verified,
                )
            )
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Operational knowledge review request policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewRequestInstruction:
    review_request_id: str
    organization_id: str
    environment_id: str
    draft_id: str
    draft_digest: str
    knowledge_item_id: str
    draft_version_id: str
    draft_artifact_id: str
    draft_schema_version: str
    draft_content_digest: str
    draft_metadata_digest: str
    provenance_digest: str
    classification: str
    access_policy_id: str
    access_policy_digest: str
    retention_policy_id: str
    retention_policy_digest: str
    encryption_profile_id: str
    encryption_profile_digest: str
    draft_item_count: int
    draft_bytes: int
    draft_created_at: datetime
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    assignment_strategy: str
    sla_class: str
    maximum_manifest_bytes: int
    orchestration_policy_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.review_request_id,
            self.organization_id,
            self.environment_id,
            self.draft_id,
            self.knowledge_item_id,
            self.draft_version_id,
            self.draft_artifact_id,
            self.draft_schema_version,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.domain_track_code,
            self.security_track_code,
            self.domain_queue_id,
            self.security_queue_id,
            self.assignment_strategy,
            self.sla_class,
        )
        if (
            self.domain_track_code != "review-track.domain"
            or self.security_track_code != "review-track.security"
            or self.domain_queue_id == self.security_queue_id
            or not 1 <= self.draft_item_count <= 1000
            or not 0 <= self.draft_bytes <= 1_048_576
            or not 1 <= self.maximum_manifest_bytes <= 262_144
            or self.draft_created_at.tzinfo is None
            or not _digests(
                self.draft_digest,
                self.draft_content_digest,
                self.draft_metadata_digest,
                self.provenance_digest,
                self.access_policy_digest,
                self.retention_policy_digest,
                self.encryption_profile_digest,
                self.orchestration_policy_digest,
            )
        ):
            raise ValueError("Operational knowledge review request instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewRequestReceipt:
    review_request_id: str
    schema_version: str
    version: int
    adapter_id: str
    attested_by: str
    draft_id: str
    draft_digest: str
    draft_content_digest: str
    manifest_id: str
    manifest_artifact_id: str
    manifest_schema_version: str
    manifest_digest: str
    routing_digest: str
    governance_digest: str
    artifact_digest: str
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    assignment_strategy: str
    sla_class: str
    domain_status: str
    security_status: str
    manifest_bytes: int
    created_at: datetime
    immutable_manifest_confirmed: bool
    encrypted_at_rest: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.review_request_id,
            self.schema_version,
            self.adapter_id,
            self.attested_by,
            self.draft_id,
            self.manifest_id,
            self.manifest_artifact_id,
            self.manifest_schema_version,
            self.domain_track_code,
            self.security_track_code,
            self.domain_queue_id,
            self.security_queue_id,
            self.assignment_strategy,
            self.sla_class,
            self.domain_status,
            self.security_status,
        )
        if (
            self.version != 1
            or self.domain_track_code != "review-track.domain"
            or self.security_track_code != "review-track.security"
            or self.domain_queue_id == self.security_queue_id
            or self.domain_status != AWAITING_REVIEWER
            or self.security_status != AWAITING_REVIEWER
            or not 1 <= self.manifest_bytes <= 262_144
            or self.created_at.tzinfo is None
            or not all(
                (
                    self.immutable_manifest_confirmed,
                    self.encrypted_at_rest,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.draft_digest,
                self.draft_content_digest,
                self.manifest_digest,
                self.routing_digest,
                self.governance_digest,
                self.artifact_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge review request receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewRequestClaim:
    claim_id: str
    schema_version: str
    version: int
    source_draft_id: str
    source_draft_digest: str
    review_request_id: str
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
            self.source_draft_id,
            self.review_request_id,
            self.organization_id,
            self.environment_id,
            self.claimed_by,
        )
        if (
            self.version != 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_draft_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge review request claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeReviewRequestRecord:
    review_request_id: str
    schema_version: str
    version: int
    claim_id: str
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
    draft_domain: str
    content_type: str
    language: str
    knowledge_lifecycle: str
    classification: str
    access_policy_id: str
    access_policy_digest: str
    retention_policy_id: str
    retention_policy_digest: str
    encryption_profile_id: str
    encryption_profile_digest: str
    draft_content_digest: str
    draft_metadata_digest: str
    provenance_digest: str
    manifest_id: str
    manifest_artifact_id: str
    manifest_schema_version: str
    manifest_digest: str
    routing_digest: str
    governance_digest: str
    artifact_digest: str
    orchestration_policy_id: str
    orchestration_policy_digest: str
    orchestration_policy_version: str
    orchestration_adapter_id: str
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    assignment_strategy: str
    sla_class: str
    domain_status: str
    security_status: str
    manifest_bytes: int
    created_at: datetime
    instance_state: str
    requested_by: str
    purpose: str
    canonical_digest: str
    review_requested: bool = True
    immutable_manifest_confirmed: bool = True
    encrypted_at_rest: bool = True
    transient_buffers_erased: bool = True
    artifact_channel_closed: bool = True
    reviewer_assigned: bool = False
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
            self.review_request_id,
            self.schema_version,
            self.claim_id,
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
            self.draft_domain,
            self.content_type,
            self.language,
            self.knowledge_lifecycle,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.manifest_id,
            self.manifest_artifact_id,
            self.manifest_schema_version,
            self.orchestration_policy_id,
            self.orchestration_policy_version,
            self.orchestration_adapter_id,
            self.domain_track_code,
            self.security_track_code,
            self.domain_queue_id,
            self.security_queue_id,
            self.assignment_strategy,
            self.sla_class,
            self.domain_status,
            self.security_status,
            self.instance_state,
            self.requested_by,
        )
        later_authority = (
            self.reviewer_assigned,
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
            or self.instance_state != OPERATIONAL_KNOWLEDGE_REVIEW_REQUESTED
            or self.knowledge_lifecycle != "review_requested"
            or self.domain_track_code != "review-track.domain"
            or self.security_track_code != "review-track.security"
            or self.domain_queue_id == self.security_queue_id
            or self.domain_status != AWAITING_REVIEWER
            or self.security_status != AWAITING_REVIEWER
            or not 1 <= len(self.title.strip()) <= 200
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 1 <= self.manifest_bytes <= 262_144
            or self.created_at.tzinfo is None
            or not _digests(
                self.source_draft_digest,
                self.access_policy_digest,
                self.retention_policy_digest,
                self.encryption_profile_digest,
                self.draft_content_digest,
                self.draft_metadata_digest,
                self.provenance_digest,
                self.manifest_digest,
                self.routing_digest,
                self.governance_digest,
                self.artifact_digest,
                self.orchestration_policy_digest,
                self.canonical_digest,
            )
            or not all(
                (
                    self.review_requested,
                    self.immutable_manifest_confirmed,
                    self.encrypted_at_rest,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                )
            )
            or any(later_authority)
        ):
            raise ValueError("Operational knowledge review request record is invalid")
