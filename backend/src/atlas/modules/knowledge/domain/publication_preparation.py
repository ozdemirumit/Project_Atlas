from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

PUBLICATION_PREPARED_STATE = "operational_knowledge_publication_prepared"
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(
            value, "operational knowledge publication preparation identifier"
        )


def _all_digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgePublicationPreparationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_resolution_schema: str
    required_resolution_state: str
    required_resolution_disposition: str
    preparation_profile_id: str
    preparation_profile_digest: str
    chunking_profile_id: str
    chunking_profile_digest: str
    embedding_profile_id: str
    embedding_profile_digest: str
    index_profile_id: str
    index_profile_digest: str
    validation_profile_id: str
    validation_profile_digest: str
    maximum_authentication_age_minutes: int
    subject_digest_salt_digest: str
    browser_binding_key_digest: str
    required_preparer_id: str
    signed_by: str
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
            self.required_resolution_schema,
            self.required_resolution_state,
            self.required_resolution_disposition,
            self.preparation_profile_id,
            self.chunking_profile_id,
            self.embedding_profile_id,
            self.index_profile_id,
            self.validation_profile_id,
            self.required_preparer_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not _all_digests(
                self.preparation_profile_digest,
                self.chunking_profile_digest,
                self.embedding_profile_digest,
                self.index_profile_digest,
                self.validation_profile_digest,
                self.subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge publication preparation policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgePublicationPreparationInstruction:
    preparation_id: str
    organization_id: str
    environment_id: str
    resolution_id: str
    resolution_digest: str
    review_request_id: str
    review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    steward_subject_digest: str
    browser_session_binding_digest: str
    policy_id: str
    policy_digest: str
    preparation_profile_id: str
    preparation_profile_digest: str
    chunking_profile_id: str
    chunking_profile_digest: str
    embedding_profile_id: str
    embedding_profile_digest: str
    index_profile_id: str
    index_profile_digest: str
    validation_profile_id: str
    validation_profile_digest: str
    purpose: str
    requested_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.preparation_id,
            self.organization_id,
            self.environment_id,
            self.resolution_id,
            self.review_request_id,
            self.source_draft_id,
            self.knowledge_item_id,
            self.policy_id,
            self.preparation_profile_id,
            self.chunking_profile_id,
            self.embedding_profile_id,
            self.index_profile_id,
            self.validation_profile_id,
        )
        if (
            not 20 <= len(self.purpose.strip()) <= 1000
            or self.requested_at.tzinfo is None
            or not _all_digests(
                self.resolution_digest,
                self.review_request_digest,
                self.source_draft_digest,
                self.steward_subject_digest,
                self.browser_session_binding_digest,
                self.policy_digest,
                self.preparation_profile_digest,
                self.chunking_profile_digest,
                self.embedding_profile_digest,
                self.index_profile_digest,
                self.validation_profile_digest,
            )
        ):
            raise ValueError("Operational knowledge publication preparation instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgePublicationPreparationReceipt:
    preparation_id: str
    schema_version: str
    version: int
    preparer_id: str
    prepared_by: str
    instruction_digest: str
    source_artifact_digest: str
    metadata_manifest_digest: str
    access_manifest_digest: str
    retention_manifest_digest: str
    prepared_at: datetime
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(self.preparation_id, self.schema_version, self.preparer_id, self.prepared_by)
        if (
            self.version != 1
            or self.prepared_at.tzinfo is None
            or not self.signature_verified
            or not _all_digests(
                self.instruction_digest,
                self.source_artifact_digest,
                self.metadata_manifest_digest,
                self.access_manifest_digest,
                self.retention_manifest_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge publication preparation receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgePublicationPreparationClaim:
    claim_id: str
    schema_version: str
    version: int
    resolution_id: str
    preparation_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.resolution_id,
            self.preparation_id,
            self.organization_id,
            self.environment_id,
        )
        if (
            self.version != 1
            or self.claimed_at.tzinfo is None
            or not _all_digests(
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge publication preparation claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgePublicationPreparationRecord:
    preparation_id: str
    schema_version: str
    version: int
    claim_id: str
    resolution_id: str
    resolution_digest: str
    review_request_id: str
    review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    final_approver_subject_digest: str
    prepared_by_subject_digest: str
    browser_session_binding_digest: str
    preparation_policy_id: str
    preparation_policy_digest: str
    preparation_policy_version: str
    preparation_profile_id: str
    preparation_profile_digest: str
    chunking_profile_id: str
    chunking_profile_digest: str
    embedding_profile_id: str
    embedding_profile_digest: str
    index_profile_id: str
    index_profile_digest: str
    validation_profile_id: str
    validation_profile_digest: str
    preparer_id: str
    preparation_receipt_digest: str
    source_artifact_digest: str
    metadata_manifest_digest: str
    access_manifest_digest: str
    retention_manifest_digest: str
    prepared_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_approved: bool = True
    publication_ready: bool = True
    publication_prepared: bool = True
    knowledge_published: bool = False
    chunks_created: bool = False
    embeddings_created: bool = False
    index_staged: bool = False
    index_validated: bool = False
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
            self.preparation_id,
            self.schema_version,
            self.claim_id,
            self.resolution_id,
            self.review_request_id,
            self.source_draft_id,
            self.knowledge_item_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.preparation_policy_id,
            self.preparation_policy_version,
            self.preparation_profile_id,
            self.chunking_profile_id,
            self.embedding_profile_id,
            self.index_profile_id,
            self.validation_profile_id,
            self.preparer_id,
            self.instance_state,
        )
        later_authority = (
            self.knowledge_published,
            self.chunks_created,
            self.embeddings_created,
            self.index_staged,
            self.index_validated,
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
            or self.instance_state != PUBLICATION_PREPARED_STATE
            or not all((self.knowledge_approved, self.publication_ready, self.publication_prepared))
            or any(later_authority)
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.prepared_at.tzinfo is None
            or not _all_digests(
                self.resolution_digest,
                self.review_request_digest,
                self.source_draft_digest,
                self.final_approver_subject_digest,
                self.prepared_by_subject_digest,
                self.browser_session_binding_digest,
                self.preparation_policy_digest,
                self.preparation_profile_digest,
                self.chunking_profile_digest,
                self.embedding_profile_digest,
                self.index_profile_digest,
                self.validation_profile_digest,
                self.preparation_receipt_digest,
                self.source_artifact_digest,
                self.metadata_manifest_digest,
                self.access_manifest_digest,
                self.retention_manifest_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge publication preparation record is invalid")
