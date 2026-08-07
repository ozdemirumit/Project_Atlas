from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

CHUNKS_CREATED_STATE = "operational_knowledge_chunks_created"
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge chunking identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeChunkingPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_materialization_schema: str
    required_materialization_state: str
    algorithm_profile_id: str
    algorithm_profile_digest: str
    maximum_chunks: int
    maximum_chunk_characters: int
    maximum_chunk_tokens: int
    maximum_overlap_characters: int
    maximum_hierarchy_depth: int
    maximum_authentication_age_minutes: int
    subject_digest_salt_digest: str
    browser_binding_key_digest: str
    required_chunker_id: str
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
            self.required_materialization_schema,
            self.required_materialization_state,
            self.algorithm_profile_id,
            self.required_chunker_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_chunks <= 100_000
            or not 1 <= self.maximum_chunk_characters <= 1_000_000
            or not 1 <= self.maximum_chunk_tokens <= 250_000
            or not 0 <= self.maximum_overlap_characters < self.maximum_chunk_characters
            or not 1 <= self.maximum_hierarchy_depth <= 64
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not _digests(
                self.algorithm_profile_digest,
                self.subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge chunking policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeChunkingInstruction:
    chunk_set_id: str
    organization_id: str
    environment_id: str
    materialization_id: str
    materialization_digest: str
    preparation_id: str
    preparation_digest: str
    knowledge_item_id: str
    source_artifact_digest: str
    protected_material_digest: str
    chunking_profile_digest: str
    governance_binding_digest: str
    media_type: str
    canonical_characters: int
    steward_subject_digest: str
    browser_session_binding_digest: str
    policy_id: str
    policy_digest: str
    algorithm_profile_id: str
    algorithm_profile_digest: str
    maximum_chunks: int
    maximum_chunk_characters: int
    maximum_chunk_tokens: int
    maximum_overlap_characters: int
    maximum_hierarchy_depth: int
    purpose: str
    requested_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.chunk_set_id,
            self.organization_id,
            self.environment_id,
            self.materialization_id,
            self.preparation_id,
            self.knowledge_item_id,
            self.policy_id,
            self.algorithm_profile_id,
        )
        if (
            not 20 <= len(self.purpose.strip()) <= 1000
            or self.requested_at.tzinfo is None
            or re.fullmatch(r"^[a-z]+/[a-z0-9.+-]+$", self.media_type) is None
            or min(
                self.canonical_characters,
                self.maximum_chunks,
                self.maximum_chunk_characters,
                self.maximum_chunk_tokens,
                self.maximum_hierarchy_depth,
            )
            < 1
            or self.maximum_overlap_characters < 0
            or not _digests(
                self.materialization_digest,
                self.preparation_digest,
                self.source_artifact_digest,
                self.protected_material_digest,
                self.chunking_profile_digest,
                self.governance_binding_digest,
                self.steward_subject_digest,
                self.browser_session_binding_digest,
                self.policy_digest,
                self.algorithm_profile_digest,
            )
        ):
            raise ValueError("Operational knowledge chunking instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeChunkingReceipt:
    chunk_set_id: str
    schema_version: str
    version: int
    chunker_id: str
    chunked_by: str
    instruction_digest: str
    materialization_digest: str
    protected_material_digest: str
    chunking_profile_digest: str
    algorithm_profile_digest: str
    ordered_chunk_manifest_digest: str
    structure_manifest_digest: str
    governance_binding_digest: str
    determinism_evidence_digest: str
    chunk_count: int
    total_chunk_characters: int
    total_chunk_tokens: int
    minimum_chunk_characters: int
    maximum_chunk_characters: int
    overlap_characters: int
    chunked_at: datetime
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(self.chunk_set_id, self.schema_version, self.chunker_id, self.chunked_by)
        if (
            self.version != 1
            or self.chunked_at.tzinfo is None
            or not self.signature_verified
            or min(
                self.chunk_count,
                self.total_chunk_characters,
                self.total_chunk_tokens,
                self.minimum_chunk_characters,
                self.maximum_chunk_characters,
            )
            < 1
            or self.minimum_chunk_characters > self.maximum_chunk_characters
            or self.overlap_characters < 0
            or not _digests(
                self.instruction_digest,
                self.materialization_digest,
                self.protected_material_digest,
                self.chunking_profile_digest,
                self.algorithm_profile_digest,
                self.ordered_chunk_manifest_digest,
                self.structure_manifest_digest,
                self.governance_binding_digest,
                self.determinism_evidence_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge chunking receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeChunkingClaim:
    claim_id: str
    schema_version: str
    version: int
    materialization_id: str
    chunk_set_id: str
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
            self.materialization_id,
            self.chunk_set_id,
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
            raise ValueError("Operational knowledge chunking claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeChunkingRecord:
    chunk_set_id: str
    schema_version: str
    version: int
    claim_id: str
    materialization_id: str
    materialization_digest: str
    preparation_id: str
    preparation_digest: str
    resolution_id: str
    resolution_digest: str
    review_request_id: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    publication_steward_subject_digest: str
    materialization_steward_subject_digest: str
    chunked_by_subject_digest: str
    browser_session_binding_digest: str
    chunking_policy_id: str
    chunking_policy_digest: str
    chunking_policy_version: str
    algorithm_profile_id: str
    algorithm_profile_digest: str
    chunker_id: str
    chunking_receipt_digest: str
    source_artifact_digest: str
    protected_material_digest: str
    chunking_profile_digest: str
    ordered_chunk_manifest_digest: str
    structure_manifest_digest: str
    governance_binding_digest: str
    determinism_evidence_digest: str
    media_type: str
    chunk_count: int
    total_chunk_characters: int
    total_chunk_tokens: int
    minimum_chunk_characters: int
    maximum_chunk_characters: int
    overlap_characters: int
    chunked_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_approved: bool = True
    publication_ready: bool = True
    publication_prepared: bool = True
    source_materialized: bool = True
    chunks_created: bool = True
    embeddings_created: bool = False
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
            self.chunk_set_id,
            self.schema_version,
            self.claim_id,
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
            self.chunking_policy_id,
            self.chunking_policy_version,
            self.algorithm_profile_id,
            self.chunker_id,
            self.instance_state,
        )
        later_authority = (
            self.embeddings_created,
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
            or self.instance_state != CHUNKS_CREATED_STATE
            or not all(
                (
                    self.knowledge_approved,
                    self.publication_ready,
                    self.publication_prepared,
                    self.source_materialized,
                    self.chunks_created,
                )
            )
            or any(later_authority)
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.chunked_at.tzinfo is None
            or re.fullmatch(r"^[a-z]+/[a-z0-9.+-]+$", self.media_type) is None
            or min(
                self.chunk_count,
                self.total_chunk_characters,
                self.total_chunk_tokens,
                self.minimum_chunk_characters,
                self.maximum_chunk_characters,
            )
            < 1
            or self.minimum_chunk_characters > self.maximum_chunk_characters
            or self.overlap_characters < 0
            or not _digests(
                self.materialization_digest,
                self.preparation_digest,
                self.resolution_digest,
                self.source_draft_digest,
                self.publication_steward_subject_digest,
                self.materialization_steward_subject_digest,
                self.chunked_by_subject_digest,
                self.browser_session_binding_digest,
                self.chunking_policy_digest,
                self.algorithm_profile_digest,
                self.chunking_receipt_digest,
                self.source_artifact_digest,
                self.protected_material_digest,
                self.chunking_profile_digest,
                self.ordered_chunk_manifest_digest,
                self.structure_manifest_digest,
                self.governance_binding_digest,
                self.determinism_evidence_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge chunking record is invalid")
