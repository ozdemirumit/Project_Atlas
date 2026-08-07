from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

RETRIEVAL_PUBLISHED_STATE = "operational_knowledge_retrieval_published"
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge publication identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeRetrievalPublicationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_index_schema: str
    required_index_state: str
    required_index_profile_digest: str
    required_staging_boundary_digest: str
    required_authorization_payload_profile_digest: str
    publication_profile_id: str
    publication_profile_digest: str
    retrieval_route_profile_digest: str
    maximum_authentication_age_minutes: int
    subject_digest_salt_digest: str
    browser_binding_key_digest: str
    required_publisher_id: str
    route_profile_owner_id: str
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
            self.required_index_schema,
            self.required_index_state,
            self.publication_profile_id,
            self.required_publisher_id,
            self.route_profile_owner_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not _digests(
                self.required_index_profile_digest,
                self.required_staging_boundary_digest,
                self.required_authorization_payload_profile_digest,
                self.publication_profile_digest,
                self.retrieval_route_profile_digest,
                self.subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge retrieval publication policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeRetrievalPublicationInstruction:
    publication_id: str
    organization_id: str
    environment_id: str
    index_staging_id: str
    index_staging_digest: str
    knowledge_item_id: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    governance_binding_digest: str
    model_profile_digest: str
    projection_manifest_digest: str
    point_coverage_digest: str
    authorization_metadata_validation_digest: str
    reconciliation_digest: str
    steward_subject_digest: str
    browser_session_binding_digest: str
    policy_id: str
    policy_digest: str
    publication_profile_id: str
    publication_profile_digest: str
    retrieval_route_profile_digest: str
    purpose: str
    requested_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.publication_id,
            self.organization_id,
            self.environment_id,
            self.index_staging_id,
            self.knowledge_item_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.policy_id,
            self.publication_profile_id,
        )
        if (
            not 20 <= len(self.purpose.strip()) <= 1000
            or self.requested_at.tzinfo is None
            or not _digests(
                self.index_staging_digest,
                self.governance_binding_digest,
                self.model_profile_digest,
                self.projection_manifest_digest,
                self.point_coverage_digest,
                self.authorization_metadata_validation_digest,
                self.reconciliation_digest,
                self.steward_subject_digest,
                self.browser_session_binding_digest,
                self.policy_digest,
                self.publication_profile_digest,
                self.retrieval_route_profile_digest,
            )
        ):
            raise ValueError("Operational knowledge retrieval publication instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeRetrievalPublicationReceipt:
    publication_id: str
    schema_version: str
    version: int
    publisher_id: str
    published_by: str
    instruction_digest: str
    index_staging_digest: str
    projection_manifest_digest: str
    publication_profile_digest: str
    retrieval_route_profile_digest: str
    route_generation_digest: str
    activation_digest: str
    route_verification_digest: str
    authorization_enforcement_digest: str
    lifecycle_filter_digest: str
    rollback_metadata_digest: str
    atomic_activation: bool
    published_at: datetime
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.publication_id,
            self.schema_version,
            self.publisher_id,
            self.published_by,
        )
        if (
            self.version != 1
            or self.published_at.tzinfo is None
            or not self.signature_verified
            or not self.atomic_activation
            or not _digests(
                self.instruction_digest,
                self.index_staging_digest,
                self.projection_manifest_digest,
                self.publication_profile_digest,
                self.retrieval_route_profile_digest,
                self.route_generation_digest,
                self.activation_digest,
                self.route_verification_digest,
                self.authorization_enforcement_digest,
                self.lifecycle_filter_digest,
                self.rollback_metadata_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge retrieval publication receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeRetrievalPublicationClaim:
    claim_id: str
    schema_version: str
    version: int
    index_staging_id: str
    publication_id: str
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
            self.index_staging_id,
            self.publication_id,
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
            raise ValueError("Operational knowledge retrieval publication claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeRetrievalPublicationRecord:
    publication_id: str
    schema_version: str
    version: int
    claim_id: str
    index_staging_id: str
    index_staging_digest: str
    embedding_set_id: str
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
    publication_steward_subject_digest: str
    browser_session_binding_digest: str
    publication_policy_id: str
    publication_policy_digest: str
    publication_policy_version: str
    publication_profile_id: str
    publication_profile_digest: str
    retrieval_route_profile_digest: str
    publisher_id: str
    publication_receipt_digest: str
    index_profile_digest: str
    staging_boundary_digest: str
    authorization_payload_profile_digest: str
    model_profile_digest: str
    governance_binding_digest: str
    projection_manifest_digest: str
    point_coverage_digest: str
    authorization_metadata_validation_digest: str
    reconciliation_digest: str
    route_generation_digest: str
    activation_digest: str
    route_verification_digest: str
    authorization_enforcement_digest: str
    lifecycle_filter_digest: str
    rollback_metadata_digest: str
    published_at: datetime
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
    knowledge_published: bool = True
    retrieval_published: bool = True
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
            self.publication_id,
            self.schema_version,
            self.claim_id,
            self.index_staging_id,
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
            self.publication_policy_id,
            self.publication_policy_version,
            self.publication_profile_id,
            self.publisher_id,
            self.instance_state,
        )
        prior = (
            self.knowledge_approved,
            self.publication_ready,
            self.publication_prepared,
            self.source_materialized,
            self.chunks_created,
            self.embeddings_created,
            self.index_staged,
            self.index_validated,
            self.knowledge_published,
            self.retrieval_published,
        )
        later = (
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
            or self.instance_state != RETRIEVAL_PUBLISHED_STATE
            or not all(prior)
            or any(later)
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.published_at.tzinfo is None
            or len(self.upstream_accountable_subject_digests) < 5
            or not _digests(
                self.index_staging_digest,
                self.publication_steward_subject_digest,
                self.browser_session_binding_digest,
                self.publication_policy_digest,
                self.publication_profile_digest,
                self.retrieval_route_profile_digest,
                self.publication_receipt_digest,
                self.index_profile_digest,
                self.staging_boundary_digest,
                self.authorization_payload_profile_digest,
                self.model_profile_digest,
                self.governance_binding_digest,
                self.projection_manifest_digest,
                self.point_coverage_digest,
                self.authorization_metadata_validation_digest,
                self.reconciliation_digest,
                self.route_generation_digest,
                self.activation_digest,
                self.route_verification_digest,
                self.authorization_enforcement_digest,
                self.lifecycle_filter_digest,
                self.rollback_metadata_digest,
                self.canonical_digest,
                *self.upstream_accountable_subject_digests,
            )
        ):
            raise ValueError("Operational knowledge retrieval publication record is invalid")
