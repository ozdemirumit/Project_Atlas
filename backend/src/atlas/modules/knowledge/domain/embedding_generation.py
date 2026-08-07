from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

EMBEDDINGS_CREATED_STATE = "operational_knowledge_embeddings_created"
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge embedding identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeEmbeddingPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_chunk_set_schema: str
    required_chunk_set_state: str
    model_profile_id: str
    model_profile_digest: str
    model_artifact_digest: str
    tokenizer_profile_digest: str
    vector_dimension: int
    normalization_profile_id: str
    distance_metric_id: str
    data_boundary_id: str
    data_boundary_digest: str
    maximum_chunks: int
    maximum_total_tokens: int
    maximum_batch_size: int
    maximum_authentication_age_minutes: int
    subject_digest_salt_digest: str
    browser_binding_key_digest: str
    required_embedder_id: str
    model_owner_id: str
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
            self.required_chunk_set_schema,
            self.required_chunk_set_state,
            self.model_profile_id,
            self.normalization_profile_id,
            self.distance_metric_id,
            self.data_boundary_id,
            self.required_embedder_id,
            self.model_owner_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.vector_dimension <= 65_536
            or not 1 <= self.maximum_chunks <= 100_000
            or not 1 <= self.maximum_total_tokens <= 100_000_000
            or not 1 <= self.maximum_batch_size <= 4096
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not _digests(
                self.model_profile_digest,
                self.model_artifact_digest,
                self.tokenizer_profile_digest,
                self.data_boundary_digest,
                self.subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge embedding policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeEmbeddingInstruction:
    embedding_set_id: str
    organization_id: str
    environment_id: str
    chunk_set_id: str
    chunk_set_digest: str
    materialization_id: str
    preparation_id: str
    knowledge_item_id: str
    protected_material_digest: str
    ordered_chunk_manifest_digest: str
    chunking_profile_digest: str
    governance_binding_digest: str
    chunk_count: int
    total_chunk_tokens: int
    steward_subject_digest: str
    browser_session_binding_digest: str
    policy_id: str
    policy_digest: str
    model_profile_id: str
    model_profile_digest: str
    model_artifact_digest: str
    tokenizer_profile_digest: str
    vector_dimension: int
    normalization_profile_id: str
    distance_metric_id: str
    data_boundary_id: str
    data_boundary_digest: str
    maximum_batch_size: int
    purpose: str
    requested_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.embedding_set_id,
            self.organization_id,
            self.environment_id,
            self.chunk_set_id,
            self.materialization_id,
            self.preparation_id,
            self.knowledge_item_id,
            self.policy_id,
            self.model_profile_id,
            self.normalization_profile_id,
            self.distance_metric_id,
            self.data_boundary_id,
        )
        if (
            not 20 <= len(self.purpose.strip()) <= 1000
            or self.requested_at.tzinfo is None
            or min(
                self.chunk_count,
                self.total_chunk_tokens,
                self.vector_dimension,
                self.maximum_batch_size,
            )
            < 1
            or not _digests(
                self.chunk_set_digest,
                self.protected_material_digest,
                self.ordered_chunk_manifest_digest,
                self.chunking_profile_digest,
                self.governance_binding_digest,
                self.steward_subject_digest,
                self.browser_session_binding_digest,
                self.policy_digest,
                self.model_profile_digest,
                self.model_artifact_digest,
                self.tokenizer_profile_digest,
                self.data_boundary_digest,
            )
        ):
            raise ValueError("Operational knowledge embedding instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeEmbeddingReceipt:
    embedding_set_id: str
    schema_version: str
    version: int
    embedder_id: str
    embedded_by: str
    instruction_digest: str
    chunk_set_digest: str
    ordered_chunk_manifest_digest: str
    model_profile_digest: str
    model_artifact_digest: str
    tokenizer_profile_digest: str
    vector_dimension: int
    normalization_profile_id: str
    distance_metric_id: str
    data_boundary_digest: str
    embedding_count: int
    vector_manifest_digest: str
    chunk_vector_binding_digest: str
    numeric_validation_digest: str
    coverage_validation_digest: str
    resource_evidence_digest: str
    embedded_at: datetime
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.embedding_set_id,
            self.schema_version,
            self.embedder_id,
            self.embedded_by,
            self.normalization_profile_id,
            self.distance_metric_id,
        )
        if (
            self.version != 1
            or self.embedded_at.tzinfo is None
            or not self.signature_verified
            or self.vector_dimension < 1
            or self.embedding_count < 1
            or not _digests(
                self.instruction_digest,
                self.chunk_set_digest,
                self.ordered_chunk_manifest_digest,
                self.model_profile_digest,
                self.model_artifact_digest,
                self.tokenizer_profile_digest,
                self.data_boundary_digest,
                self.vector_manifest_digest,
                self.chunk_vector_binding_digest,
                self.numeric_validation_digest,
                self.coverage_validation_digest,
                self.resource_evidence_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge embedding receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeEmbeddingClaim:
    claim_id: str
    schema_version: str
    version: int
    chunk_set_id: str
    embedding_set_id: str
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
            self.chunk_set_id,
            self.embedding_set_id,
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
            raise ValueError("Operational knowledge embedding claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeEmbeddingRecord:
    embedding_set_id: str
    schema_version: str
    version: int
    claim_id: str
    chunk_set_id: str
    chunk_set_digest: str
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
    publication_steward_subject_digest: str
    materialization_steward_subject_digest: str
    chunking_steward_subject_digest: str
    embedded_by_subject_digest: str
    browser_session_binding_digest: str
    embedding_policy_id: str
    embedding_policy_digest: str
    embedding_policy_version: str
    model_profile_id: str
    model_profile_digest: str
    model_artifact_digest: str
    tokenizer_profile_digest: str
    vector_dimension: int
    normalization_profile_id: str
    distance_metric_id: str
    data_boundary_id: str
    data_boundary_digest: str
    embedder_id: str
    embedding_receipt_digest: str
    protected_material_digest: str
    ordered_chunk_manifest_digest: str
    chunking_profile_digest: str
    governance_binding_digest: str
    embedding_count: int
    vector_manifest_digest: str
    chunk_vector_binding_digest: str
    numeric_validation_digest: str
    coverage_validation_digest: str
    resource_evidence_digest: str
    embedded_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_approved: bool = True
    publication_ready: bool = True
    publication_prepared: bool = True
    source_materialized: bool = True
    chunks_created: bool = True
    embeddings_created: bool = True
    index_staged: bool = False
    index_validated: bool = False
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
            self.embedding_set_id,
            self.schema_version,
            self.claim_id,
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
            self.embedding_policy_id,
            self.embedding_policy_version,
            self.model_profile_id,
            self.normalization_profile_id,
            self.distance_metric_id,
            self.data_boundary_id,
            self.embedder_id,
            self.instance_state,
        )
        later = (
            self.index_staged,
            self.index_validated,
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
            or self.instance_state != EMBEDDINGS_CREATED_STATE
            or not all(
                (
                    self.knowledge_approved,
                    self.publication_ready,
                    self.publication_prepared,
                    self.source_materialized,
                    self.chunks_created,
                    self.embeddings_created,
                )
            )
            or any(later)
            or self.vector_dimension < 1
            or self.embedding_count < 1
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.embedded_at.tzinfo is None
            or not _digests(
                self.chunk_set_digest,
                self.publication_steward_subject_digest,
                self.materialization_steward_subject_digest,
                self.chunking_steward_subject_digest,
                self.embedded_by_subject_digest,
                self.browser_session_binding_digest,
                self.embedding_policy_digest,
                self.model_profile_digest,
                self.model_artifact_digest,
                self.tokenizer_profile_digest,
                self.data_boundary_digest,
                self.embedding_receipt_digest,
                self.protected_material_digest,
                self.ordered_chunk_manifest_digest,
                self.chunking_profile_digest,
                self.governance_binding_digest,
                self.vector_manifest_digest,
                self.chunk_vector_binding_digest,
                self.numeric_validation_digest,
                self.coverage_validation_digest,
                self.resource_evidence_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge embedding record is invalid")
