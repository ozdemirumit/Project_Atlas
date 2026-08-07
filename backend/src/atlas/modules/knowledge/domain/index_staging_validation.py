from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

INDEX_VALIDATED_STATE = "operational_knowledge_index_validated"
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge index identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeIndexPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_embedding_set_schema: str
    required_embedding_set_state: str
    required_model_profile_digest: str
    required_vector_dimension: int
    required_normalization_profile_id: str
    required_distance_metric_id: str
    index_profile_id: str
    index_profile_digest: str
    staging_boundary_id: str
    staging_boundary_digest: str
    authorization_payload_profile_digest: str
    maximum_points: int
    maximum_batch_size: int
    maximum_authentication_age_minutes: int
    subject_digest_salt_digest: str
    browser_binding_key_digest: str
    required_indexer_id: str
    index_profile_owner_id: str
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
            self.required_embedding_set_schema,
            self.required_embedding_set_state,
            self.required_normalization_profile_id,
            self.required_distance_metric_id,
            self.index_profile_id,
            self.staging_boundary_id,
            self.required_indexer_id,
            self.index_profile_owner_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.required_vector_dimension <= 65_536
            or not 1 <= self.maximum_points <= 100_000
            or not 1 <= self.maximum_batch_size <= 4096
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not _digests(
                self.required_model_profile_digest,
                self.index_profile_digest,
                self.staging_boundary_digest,
                self.authorization_payload_profile_digest,
                self.subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge index policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeIndexInstruction:
    index_staging_id: str
    organization_id: str
    environment_id: str
    embedding_set_id: str
    embedding_set_digest: str
    chunk_set_id: str
    knowledge_item_id: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    governance_binding_digest: str
    model_profile_digest: str
    vector_dimension: int
    normalization_profile_id: str
    distance_metric_id: str
    embedding_count: int
    vector_manifest_digest: str
    chunk_vector_binding_digest: str
    steward_subject_digest: str
    browser_session_binding_digest: str
    policy_id: str
    policy_digest: str
    index_profile_id: str
    index_profile_digest: str
    staging_boundary_id: str
    staging_boundary_digest: str
    authorization_payload_profile_digest: str
    maximum_batch_size: int
    purpose: str
    requested_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.index_staging_id,
            self.organization_id,
            self.environment_id,
            self.embedding_set_id,
            self.chunk_set_id,
            self.knowledge_item_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.normalization_profile_id,
            self.distance_metric_id,
            self.policy_id,
            self.index_profile_id,
            self.staging_boundary_id,
        )
        if (
            not 20 <= len(self.purpose.strip()) <= 1000
            or self.requested_at.tzinfo is None
            or min(self.vector_dimension, self.embedding_count, self.maximum_batch_size) < 1
            or not _digests(
                self.embedding_set_digest,
                self.governance_binding_digest,
                self.model_profile_digest,
                self.vector_manifest_digest,
                self.chunk_vector_binding_digest,
                self.steward_subject_digest,
                self.browser_session_binding_digest,
                self.policy_digest,
                self.index_profile_digest,
                self.staging_boundary_digest,
                self.authorization_payload_profile_digest,
            )
        ):
            raise ValueError("Operational knowledge index instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeIndexReceipt:
    index_staging_id: str
    schema_version: str
    version: int
    indexer_id: str
    indexed_by: str
    instruction_digest: str
    embedding_set_digest: str
    model_profile_digest: str
    vector_dimension: int
    normalization_profile_id: str
    distance_metric_id: str
    index_profile_digest: str
    staging_boundary_digest: str
    expected_point_count: int
    staged_point_count: int
    projection_manifest_digest: str
    point_coverage_digest: str
    authorization_metadata_validation_digest: str
    model_compatibility_validation_digest: str
    isolation_validation_digest: str
    reconciliation_digest: str
    projection_sealed: bool
    validated_at: datetime
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.index_staging_id,
            self.schema_version,
            self.indexer_id,
            self.indexed_by,
            self.normalization_profile_id,
            self.distance_metric_id,
        )
        if (
            self.version != 1
            or self.validated_at.tzinfo is None
            or not self.signature_verified
            or not self.projection_sealed
            or self.vector_dimension < 1
            or min(self.expected_point_count, self.staged_point_count) < 1
            or not _digests(
                self.instruction_digest,
                self.embedding_set_digest,
                self.model_profile_digest,
                self.index_profile_digest,
                self.staging_boundary_digest,
                self.projection_manifest_digest,
                self.point_coverage_digest,
                self.authorization_metadata_validation_digest,
                self.model_compatibility_validation_digest,
                self.isolation_validation_digest,
                self.reconciliation_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge index receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeIndexClaim:
    claim_id: str
    schema_version: str
    version: int
    embedding_set_id: str
    index_staging_id: str
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
            self.embedding_set_id,
            self.index_staging_id,
            self.organization_id,
            self.environment_id,
        )
        if (
            self.version != 1
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge index claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeIndexRecord:
    index_staging_id: str
    schema_version: str
    version: int
    claim_id: str
    embedding_set_id: str
    embedding_set_digest: str
    chunk_set_id: str
    materialization_id: str
    preparation_id: str
    resolution_id: str
    review_request_id: str
    source_draft_id: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    index_steward_subject_digest: str
    browser_session_binding_digest: str
    index_policy_id: str
    index_policy_digest: str
    index_policy_version: str
    index_profile_id: str
    index_profile_digest: str
    staging_boundary_id: str
    staging_boundary_digest: str
    authorization_payload_profile_digest: str
    indexer_id: str
    index_receipt_digest: str
    model_profile_digest: str
    vector_dimension: int
    normalization_profile_id: str
    distance_metric_id: str
    embedding_count: int
    vector_manifest_digest: str
    chunk_vector_binding_digest: str
    governance_binding_digest: str
    staged_point_count: int
    projection_manifest_digest: str
    point_coverage_digest: str
    authorization_metadata_validation_digest: str
    model_compatibility_validation_digest: str
    isolation_validation_digest: str
    reconciliation_digest: str
    validated_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    upstream_accountable_subject_digests: tuple[str, ...]
    knowledge_approved: bool = True
    publication_ready: bool = True
    publication_prepared: bool = True
    source_materialized: bool = True
    chunks_created: bool = True
    embeddings_created: bool = True
    index_staged: bool = True
    index_validated: bool = True
    knowledge_published: bool = False
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
            self.index_staging_id,
            self.schema_version,
            self.claim_id,
            self.embedding_set_id,
            self.chunk_set_id,
            self.materialization_id,
            self.preparation_id,
            self.resolution_id,
            self.review_request_id,
            self.source_draft_id,
            self.knowledge_item_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.index_policy_id,
            self.index_policy_version,
            self.index_profile_id,
            self.staging_boundary_id,
            self.indexer_id,
            self.normalization_profile_id,
            self.distance_metric_id,
            self.instance_state,
        )
        later = (
            self.knowledge_published,
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
            or self.instance_state != INDEX_VALIDATED_STATE
            or not all(
                (
                    self.knowledge_approved,
                    self.publication_ready,
                    self.publication_prepared,
                    self.source_materialized,
                    self.chunks_created,
                    self.embeddings_created,
                    self.index_staged,
                    self.index_validated,
                )
            )
            or any(later)
            or self.vector_dimension < 1
            or self.embedding_count < 1
            or self.staged_point_count != self.embedding_count
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.validated_at.tzinfo is None
            or len(self.upstream_accountable_subject_digests) < 4
            or not _digests(
                self.embedding_set_digest,
                self.index_steward_subject_digest,
                self.browser_session_binding_digest,
                self.index_policy_digest,
                self.index_profile_digest,
                self.staging_boundary_digest,
                self.authorization_payload_profile_digest,
                self.index_receipt_digest,
                self.model_profile_digest,
                self.vector_manifest_digest,
                self.chunk_vector_binding_digest,
                self.governance_binding_digest,
                self.projection_manifest_digest,
                self.point_coverage_digest,
                self.authorization_metadata_validation_digest,
                self.model_compatibility_validation_digest,
                self.isolation_validation_digest,
                self.reconciliation_digest,
                self.canonical_digest,
                *self.upstream_accountable_subject_digests,
            )
        ):
            raise ValueError("Operational knowledge index record is invalid")
