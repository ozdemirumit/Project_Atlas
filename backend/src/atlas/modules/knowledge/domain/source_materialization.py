from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

SOURCE_MATERIALIZED_STATE = "operational_knowledge_source_materialized"
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge source materialization identifier")


def _all_digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeSourceMaterializationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_preparation_schema: str
    required_preparation_state: str
    canonicalization_profile_id: str
    canonicalization_profile_digest: str
    source_security_profile_id: str
    source_security_profile_digest: str
    media_type_allowlist_digest: str
    maximum_source_bytes: int
    maximum_canonical_characters: int
    maximum_authentication_age_minutes: int
    subject_digest_salt_digest: str
    browser_binding_key_digest: str
    required_materializer_id: str
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
            self.required_preparation_schema,
            self.required_preparation_state,
            self.canonicalization_profile_id,
            self.source_security_profile_id,
            self.required_materializer_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_source_bytes <= 100_000_000
            or not 1 <= self.maximum_canonical_characters <= 50_000_000
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not _all_digests(
                self.canonicalization_profile_digest,
                self.source_security_profile_digest,
                self.media_type_allowlist_digest,
                self.subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge source materialization policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeSourceMaterializationInstruction:
    materialization_id: str
    organization_id: str
    environment_id: str
    preparation_id: str
    preparation_digest: str
    resolution_id: str
    resolution_digest: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    source_artifact_digest: str
    metadata_manifest_digest: str
    access_manifest_digest: str
    retention_manifest_digest: str
    chunking_profile_digest: str
    embedding_profile_digest: str
    index_profile_digest: str
    validation_profile_digest: str
    steward_subject_digest: str
    browser_session_binding_digest: str
    policy_id: str
    policy_digest: str
    canonicalization_profile_id: str
    canonicalization_profile_digest: str
    source_security_profile_id: str
    source_security_profile_digest: str
    media_type_allowlist_digest: str
    maximum_source_bytes: int
    maximum_canonical_characters: int
    purpose: str
    requested_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.materialization_id,
            self.organization_id,
            self.environment_id,
            self.preparation_id,
            self.resolution_id,
            self.source_draft_id,
            self.knowledge_item_id,
            self.policy_id,
            self.canonicalization_profile_id,
            self.source_security_profile_id,
        )
        if (
            not 20 <= len(self.purpose.strip()) <= 1000
            or self.requested_at.tzinfo is None
            or self.maximum_source_bytes < 1
            or self.maximum_canonical_characters < 1
            or not _all_digests(
                self.preparation_digest,
                self.resolution_digest,
                self.source_draft_digest,
                self.source_artifact_digest,
                self.metadata_manifest_digest,
                self.access_manifest_digest,
                self.retention_manifest_digest,
                self.chunking_profile_digest,
                self.embedding_profile_digest,
                self.index_profile_digest,
                self.validation_profile_digest,
                self.steward_subject_digest,
                self.browser_session_binding_digest,
                self.policy_digest,
                self.canonicalization_profile_digest,
                self.source_security_profile_digest,
                self.media_type_allowlist_digest,
            )
        ):
            raise ValueError("Operational knowledge source materialization instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeSourceMaterializationReceipt:
    materialization_id: str
    schema_version: str
    version: int
    materializer_id: str
    materialized_by: str
    instruction_digest: str
    source_artifact_digest: str
    protected_material_digest: str
    canonicalization_profile_digest: str
    media_type: str
    source_bytes: int
    canonical_bytes: int
    canonical_characters: int
    security_scan_evidence_digest: str
    governance_binding_digest: str
    materialized_at: datetime
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.materialization_id,
            self.schema_version,
            self.materializer_id,
            self.materialized_by,
        )
        if (
            self.version != 1
            or self.materialized_at.tzinfo is None
            or not self.signature_verified
            or re.fullmatch(r"^[a-z]+/[a-z0-9.+-]+$", self.media_type) is None
            or self.source_bytes < 1
            or self.canonical_bytes < 1
            or self.canonical_characters < 1
            or not _all_digests(
                self.instruction_digest,
                self.source_artifact_digest,
                self.protected_material_digest,
                self.canonicalization_profile_digest,
                self.security_scan_evidence_digest,
                self.governance_binding_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge source materialization receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeSourceMaterializationClaim:
    claim_id: str
    schema_version: str
    version: int
    preparation_id: str
    materialization_id: str
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
            self.preparation_id,
            self.materialization_id,
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
            raise ValueError("Operational knowledge source materialization claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeSourceMaterializationRecord:
    materialization_id: str
    schema_version: str
    version: int
    claim_id: str
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
    materialized_by_subject_digest: str
    browser_session_binding_digest: str
    materialization_policy_id: str
    materialization_policy_digest: str
    materialization_policy_version: str
    canonicalization_profile_id: str
    canonicalization_profile_digest: str
    source_security_profile_id: str
    source_security_profile_digest: str
    materializer_id: str
    materialization_receipt_digest: str
    source_artifact_digest: str
    protected_material_digest: str
    media_type: str
    source_bytes: int
    canonical_bytes: int
    canonical_characters: int
    security_scan_evidence_digest: str
    governance_binding_digest: str
    materialized_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_approved: bool = True
    publication_ready: bool = True
    publication_prepared: bool = True
    source_materialized: bool = True
    chunks_created: bool = False
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
            self.materialization_id,
            self.schema_version,
            self.claim_id,
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
            self.materialization_policy_id,
            self.materialization_policy_version,
            self.canonicalization_profile_id,
            self.source_security_profile_id,
            self.materializer_id,
            self.instance_state,
        )
        later_authority = (
            self.chunks_created,
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
            or self.instance_state != SOURCE_MATERIALIZED_STATE
            or not all(
                (
                    self.knowledge_approved,
                    self.publication_ready,
                    self.publication_prepared,
                    self.source_materialized,
                )
            )
            or any(later_authority)
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.materialized_at.tzinfo is None
            or re.fullmatch(r"^[a-z]+/[a-z0-9.+-]+$", self.media_type) is None
            or min(self.source_bytes, self.canonical_bytes, self.canonical_characters) < 1
            or not _all_digests(
                self.preparation_digest,
                self.resolution_digest,
                self.source_draft_digest,
                self.publication_steward_subject_digest,
                self.materialized_by_subject_digest,
                self.browser_session_binding_digest,
                self.materialization_policy_digest,
                self.canonicalization_profile_digest,
                self.source_security_profile_digest,
                self.materialization_receipt_digest,
                self.source_artifact_digest,
                self.protected_material_digest,
                self.security_scan_evidence_digest,
                self.governance_binding_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge source materialization record is invalid")
