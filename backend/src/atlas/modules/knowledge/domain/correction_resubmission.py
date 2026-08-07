from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
TRACKS = frozenset(("review-track.domain", "review-track.security"))
AWAITING_REVIEWER = "awaiting_reviewer"
OPERATIONAL_KNOWLEDGE_CORRECTION_RESUBMITTED = "operational_knowledge_correction_resubmitted"


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge correction identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeCorrectionPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_decision_schema: str
    required_decision_state: str
    required_request_schema: str
    required_request_state: str
    required_draft_schema: str
    required_draft_state: str
    required_adapter_id: str
    required_adapter_attestor_id: str
    required_receipt_schema: str
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    assignment_strategy: str
    sla_class: str
    maximum_authentication_age_minutes: int
    maximum_draft_items: int
    maximum_draft_bytes: int
    maximum_manifest_bytes: int
    subject_digest_salt_digest: str
    browser_binding_key_digest: str
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
            self.required_decision_schema,
            self.required_decision_state,
            self.required_request_schema,
            self.required_request_state,
            self.required_draft_schema,
            self.required_draft_state,
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
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 1 <= self.maximum_draft_items <= 1000
            or not 1 <= self.maximum_draft_bytes <= 1_048_576
            or not 1 <= self.maximum_manifest_bytes <= 262_144
            or self.required_assurance_level is not AssuranceLevel.HARDWARE_BACKED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(
                self.subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge correction policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeCorrectionInstruction:
    correction_id: str
    source_review_request_id: str
    source_review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    source_decision_ids: tuple[str, str]
    source_decision_digests: tuple[str, str]
    decision_aggregate_digest: str
    correction_submission_id: str
    correction_submission_digest: str
    organization_id: str
    environment_id: str
    knowledge_item_id: str
    prior_draft_version_id: str
    title: str
    draft_domain: str
    content_type: str
    language: str
    classification: str
    access_policy_id: str
    access_policy_digest: str
    retention_policy_id: str
    retention_policy_digest: str
    encryption_profile_id: str
    encryption_profile_digest: str
    new_draft_id: str
    new_draft_version_id: str
    new_review_request_id: str
    review_generation: int
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    assignment_strategy: str
    sla_class: str
    maximum_draft_items: int
    maximum_draft_bytes: int
    maximum_manifest_bytes: int
    corrected_by_subject_digest: str
    browser_session_binding_digest: str
    correction_policy_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.correction_id,
            self.source_review_request_id,
            self.source_draft_id,
            *self.source_decision_ids,
            self.correction_submission_id,
            self.organization_id,
            self.environment_id,
            self.knowledge_item_id,
            self.prior_draft_version_id,
            self.draft_domain,
            self.content_type,
            self.language,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.new_draft_id,
            self.new_draft_version_id,
            self.new_review_request_id,
            self.domain_track_code,
            self.security_track_code,
            self.domain_queue_id,
            self.security_queue_id,
            self.assignment_strategy,
            self.sla_class,
        )
        if (
            len(set(self.source_decision_ids)) != 2
            or len(set(self.source_decision_digests)) != 2
            or self.review_generation < 2
            or self.domain_track_code != "review-track.domain"
            or self.security_track_code != "review-track.security"
            or self.domain_queue_id == self.security_queue_id
            or not 1 <= len(self.title.strip()) <= 200
            or not 1 <= self.maximum_draft_items <= 1000
            or not 1 <= self.maximum_draft_bytes <= 1_048_576
            or not 1 <= self.maximum_manifest_bytes <= 262_144
            or not _digests(
                self.source_review_request_digest,
                self.source_draft_digest,
                *self.source_decision_digests,
                self.decision_aggregate_digest,
                self.correction_submission_digest,
                self.access_policy_digest,
                self.retention_policy_digest,
                self.encryption_profile_digest,
                self.corrected_by_subject_digest,
                self.browser_session_binding_digest,
                self.correction_policy_digest,
            )
        ):
            raise ValueError("Operational knowledge correction instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeCorrectionReceipt:
    correction_id: str
    schema_version: str
    version: int
    adapter_id: str
    attested_by: str
    source_review_request_id: str
    source_review_request_digest: str
    decision_aggregate_digest: str
    correction_submission_id: str
    correction_submission_digest: str
    new_draft_id: str
    new_draft_version_id: str
    new_draft_artifact_id: str
    new_draft_schema_version: str
    new_draft_content_digest: str
    new_draft_metadata_digest: str
    new_provenance_digest: str
    new_draft_item_count: int
    new_draft_bytes: int
    new_review_request_id: str
    new_manifest_id: str
    new_manifest_artifact_id: str
    new_manifest_schema_version: str
    new_manifest_digest: str
    new_routing_digest: str
    new_governance_digest: str
    new_artifact_digest: str
    domain_status: str
    security_status: str
    manifest_bytes: int
    created_at: datetime
    immutable_draft_confirmed: bool
    immutable_manifest_confirmed: bool
    encrypted_at_rest: bool
    transient_buffers_erased: bool
    artifact_channel_closed: bool
    signature_verified: bool
    instruction_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.correction_id,
            self.schema_version,
            self.adapter_id,
            self.attested_by,
            self.source_review_request_id,
            self.correction_submission_id,
            self.new_draft_id,
            self.new_draft_version_id,
            self.new_draft_artifact_id,
            self.new_draft_schema_version,
            self.new_review_request_id,
            self.new_manifest_id,
            self.new_manifest_artifact_id,
            self.new_manifest_schema_version,
            self.domain_status,
            self.security_status,
        )
        if (
            self.version != 1
            or self.domain_status != AWAITING_REVIEWER
            or self.security_status != AWAITING_REVIEWER
            or not 1 <= self.new_draft_item_count <= 1000
            or not 0 <= self.new_draft_bytes <= 1_048_576
            or not 1 <= self.manifest_bytes <= 262_144
            or self.created_at.tzinfo is None
            or not all(
                (
                    self.immutable_draft_confirmed,
                    self.immutable_manifest_confirmed,
                    self.encrypted_at_rest,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.source_review_request_digest,
                self.decision_aggregate_digest,
                self.correction_submission_digest,
                self.new_draft_content_digest,
                self.new_draft_metadata_digest,
                self.new_provenance_digest,
                self.new_manifest_digest,
                self.new_routing_digest,
                self.new_governance_digest,
                self.new_artifact_digest,
                self.instruction_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge correction receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeCorrectionClaim:
    claim_id: str
    schema_version: str
    version: int
    source_review_request_id: str
    source_review_request_digest: str
    correction_id: str
    organization_id: str
    environment_id: str
    decision_aggregate_digest: str
    correction_submission_digest: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    purpose_digest: str
    claimed_at: datetime
    request_binding_digest: str
    idempotency_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.source_review_request_id,
            self.correction_id,
            self.organization_id,
            self.environment_id,
        )
        if (
            self.version != 1
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_review_request_digest,
                self.decision_aggregate_digest,
                self.correction_submission_digest,
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.purpose_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge correction claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeCorrectionRecord:
    correction_id: str
    schema_version: str
    version: int
    claim_id: str
    source_review_request_id: str
    source_review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    source_decision_ids: tuple[str, str]
    source_decision_digests: tuple[str, str]
    decision_aggregate_digest: str
    organization_id: str
    environment_id: str
    knowledge_item_id: str
    prior_draft_version_id: str
    title: str
    classification: str
    access_policy_id: str
    access_policy_digest: str
    retention_policy_id: str
    retention_policy_digest: str
    encryption_profile_id: str
    encryption_profile_digest: str
    correction_submission_id: str
    correction_submission_digest: str
    corrected_by_subject_digest: str
    browser_session_binding_digest: str
    correction_policy_id: str
    correction_policy_digest: str
    correction_policy_version: str
    adapter_id: str
    attestation_digest: str
    new_draft_id: str
    new_draft_version_id: str
    new_draft_artifact_id: str
    new_draft_schema_version: str
    new_draft_content_digest: str
    new_draft_metadata_digest: str
    new_provenance_digest: str
    new_draft_item_count: int
    new_draft_bytes: int
    new_review_request_id: str
    new_manifest_id: str
    new_manifest_artifact_id: str
    new_manifest_schema_version: str
    new_manifest_digest: str
    new_routing_digest: str
    new_governance_digest: str
    new_artifact_digest: str
    domain_track_code: str
    security_track_code: str
    domain_queue_id: str
    security_queue_id: str
    assignment_strategy: str
    sla_class: str
    domain_status: str
    security_status: str
    review_generation: int
    manifest_bytes: int
    created_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    correction_created: bool = True
    corrected_draft_created: bool = True
    review_resubmitted: bool = True
    immutable_draft_confirmed: bool = True
    immutable_manifest_confirmed: bool = True
    encrypted_at_rest: bool = True
    transient_buffers_erased: bool = True
    artifact_channel_closed: bool = True
    reviewer_assigned: bool = False
    content_inspection_opened: bool = False
    domain_review_completed: bool = False
    security_review_completed: bool = False
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
            self.correction_id,
            self.schema_version,
            self.claim_id,
            self.source_review_request_id,
            self.source_draft_id,
            *self.source_decision_ids,
            self.organization_id,
            self.environment_id,
            self.knowledge_item_id,
            self.prior_draft_version_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.encryption_profile_id,
            self.correction_submission_id,
            self.correction_policy_id,
            self.correction_policy_version,
            self.adapter_id,
            self.new_draft_id,
            self.new_draft_version_id,
            self.new_draft_artifact_id,
            self.new_draft_schema_version,
            self.new_review_request_id,
            self.new_manifest_id,
            self.new_manifest_artifact_id,
            self.new_manifest_schema_version,
            self.domain_track_code,
            self.security_track_code,
            self.domain_queue_id,
            self.security_queue_id,
            self.assignment_strategy,
            self.sla_class,
            self.domain_status,
            self.security_status,
            self.instance_state,
        )
        later_authority = (
            self.reviewer_assigned,
            self.content_inspection_opened,
            self.domain_review_completed,
            self.security_review_completed,
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
            or self.instance_state != OPERATIONAL_KNOWLEDGE_CORRECTION_RESUBMITTED
            or len(set(self.source_decision_ids)) != 2
            or len(set(self.source_decision_digests)) != 2
            or self.review_generation < 2
            or self.domain_track_code != "review-track.domain"
            or self.security_track_code != "review-track.security"
            or self.domain_status != AWAITING_REVIEWER
            or self.security_status != AWAITING_REVIEWER
            or not 1 <= len(self.title.strip()) <= 200
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not 1 <= self.new_draft_item_count <= 1000
            or not 0 <= self.new_draft_bytes <= 1_048_576
            or not 1 <= self.manifest_bytes <= 262_144
            or self.created_at.tzinfo is None
            or not all(
                (
                    self.correction_created,
                    self.corrected_draft_created,
                    self.review_resubmitted,
                    self.immutable_draft_confirmed,
                    self.immutable_manifest_confirmed,
                    self.encrypted_at_rest,
                    self.transient_buffers_erased,
                    self.artifact_channel_closed,
                )
            )
            or any(later_authority)
            or not _digests(
                self.source_review_request_digest,
                self.source_draft_digest,
                *self.source_decision_digests,
                self.decision_aggregate_digest,
                self.access_policy_digest,
                self.retention_policy_digest,
                self.encryption_profile_digest,
                self.correction_submission_digest,
                self.corrected_by_subject_digest,
                self.browser_session_binding_digest,
                self.correction_policy_digest,
                self.attestation_digest,
                self.new_draft_content_digest,
                self.new_draft_metadata_digest,
                self.new_provenance_digest,
                self.new_manifest_digest,
                self.new_routing_digest,
                self.new_governance_digest,
                self.new_artifact_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge correction record is invalid")
