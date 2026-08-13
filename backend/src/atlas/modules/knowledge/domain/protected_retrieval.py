from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
RETRIEVED_STATE = "operational_knowledge_retrieved"


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge retrieval identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeRetrievalPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_publication_schema: str
    required_publication_state: str
    required_retriever_id: str
    required_retriever_attestor_id: str
    required_receipt_schema: str
    protected_vault_id: str
    retrieval_profile_digest: str
    authorization_profile_digest: str
    ranking_profile_digest: str
    evidence_profile_digest: str
    subject_digest_salt_digest: str
    browser_binding_key_digest: str
    maximum_authentication_age_minutes: int
    maximum_query_characters: int
    maximum_results: int
    maximum_excerpt_characters: int
    retention_minutes: int
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
            self.required_publication_schema,
            self.required_publication_state,
            self.required_retriever_id,
            self.required_retriever_attestor_id,
            self.required_receipt_schema,
            self.protected_vault_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 64 <= self.maximum_query_characters <= 4_000
            or not 1 <= self.maximum_results <= 20
            or not 128 <= self.maximum_excerpt_characters <= 4_000
            or not 1 <= self.retention_minutes <= 1_440
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
            or not _digests(
                self.retrieval_profile_digest,
                self.authorization_profile_digest,
                self.ranking_profile_digest,
                self.evidence_profile_digest,
                self.subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge retrieval policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeRetrievalInstruction:
    retrieval_id: str
    organization_id: str
    environment_id: str
    publication_id: str
    publication_digest: str
    route_generation_digest: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    consumer_subject_digest: str
    authorization_context_digest: str
    browser_session_binding_digest: str
    query: str
    query_digest: str
    purpose: str
    policy_id: str
    policy_digest: str
    retrieval_profile_digest: str
    authorization_profile_digest: str
    ranking_profile_digest: str
    evidence_profile_digest: str
    maximum_results: int
    maximum_excerpt_characters: int
    protected_vault_id: str
    requested_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.retrieval_id,
            self.organization_id,
            self.environment_id,
            self.publication_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.policy_id,
            self.protected_vault_id,
        )
        if (
            not 3 <= len(self.query.strip()) <= 4_000
            or not 20 <= len(self.purpose.strip()) <= 1_000
            or not 1 <= self.maximum_results <= 20
            or not 128 <= self.maximum_excerpt_characters <= 4_000
            or self.requested_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.requested_at < self.expires_at
            or not _digests(
                self.publication_digest,
                self.route_generation_digest,
                self.consumer_subject_digest,
                self.authorization_context_digest,
                self.browser_session_binding_digest,
                self.query_digest,
                self.policy_digest,
                self.retrieval_profile_digest,
                self.authorization_profile_digest,
                self.ranking_profile_digest,
                self.evidence_profile_digest,
            )
        ):
            raise ValueError("Operational knowledge retrieval instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeEvidenceResult:
    evidence_reference_id: str
    source_title: str
    source_class: str
    excerpt: str
    citation_location: str
    applicability: str
    lifecycle_state: str
    freshness_state: str
    conflict_state: str
    safety_state: str
    rank_band: str

    def __post_init__(self) -> None:
        _ids(
            self.evidence_reference_id,
            self.source_class,
            self.lifecycle_state,
            self.freshness_state,
            self.conflict_state,
            self.safety_state,
            self.rank_band,
        )
        if not all(
            (
                1 <= len(self.source_title.strip()) <= 300,
                1 <= len(self.excerpt.strip()) <= 4_000,
                1 <= len(self.citation_location.strip()) <= 300,
                1 <= len(self.applicability.strip()) <= 500,
            )
        ):
            raise ValueError("Operational knowledge evidence result is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeEvidencePackage:
    retrieval_id: str
    query: str
    results: tuple[OperationalKnowledgeEvidenceResult, ...]
    outcome: str
    generated_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(self.retrieval_id, self.outcome)
        if (
            not 3 <= len(self.query.strip()) <= 4_000
            or len(self.results) > 20
            or self.generated_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.generated_at < self.expires_at
            or self.outcome
            not in {
                "retrieval-outcome.evidence-available",
                "retrieval-outcome.insufficient-evidence",
            }
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Operational knowledge evidence package is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeRetrievalReceipt:
    retrieval_id: str
    schema_version: str
    version: int
    retriever_id: str
    attested_by: str
    publication_id: str
    publication_digest: str
    consumer_subject_digest: str
    query_digest: str
    authorization_context_digest: str
    evidence_package_digest: str
    protected_artifact_reference: str
    protected_artifact_digest: str
    result_count: int
    outcome: str
    authorization_filter_digest: str
    ranking_digest: str
    citation_validation_digest: str
    safety_validation_digest: str
    retrieved_at: datetime
    expires_at: datetime
    authorization_filtered_before_scoring: bool
    citations_validated: bool
    protected_vault_write_verified: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.retrieval_id,
            self.schema_version,
            self.retriever_id,
            self.attested_by,
            self.publication_id,
            self.protected_artifact_reference,
            self.outcome,
        )
        if (
            self.version != 1
            or not 0 <= self.result_count <= 20
            or self.retrieved_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.retrieved_at < self.expires_at
            or not all(
                (
                    self.authorization_filtered_before_scoring,
                    self.citations_validated,
                    self.protected_vault_write_verified,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.publication_digest,
                self.consumer_subject_digest,
                self.query_digest,
                self.authorization_context_digest,
                self.evidence_package_digest,
                self.protected_artifact_digest,
                self.authorization_filter_digest,
                self.ranking_digest,
                self.citation_validation_digest,
                self.safety_validation_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge retrieval receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeRetrievalClaim:
    claim_id: str
    schema_version: str
    version: int
    retrieval_id: str
    publication_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    query_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.retrieval_id,
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
                self.query_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge retrieval claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeRetrievalRecord:
    retrieval_id: str
    schema_version: str
    version: int
    claim_id: str
    publication_id: str
    publication_digest: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    retrieval_policy_id: str
    retrieval_policy_digest: str
    retrieval_policy_version: str
    retriever_id: str
    retrieval_receipt_digest: str
    query_digest: str
    authorization_context_digest: str
    evidence_package_digest: str
    protected_artifact_reference: str
    protected_artifact_digest: str
    result_count: int
    outcome: str
    retrieved_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_retrieved: bool = True
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
            self.retrieval_id,
            self.schema_version,
            self.claim_id,
            self.publication_id,
            self.knowledge_item_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.retrieval_policy_id,
            self.retrieval_policy_version,
            self.retriever_id,
            self.protected_artifact_reference,
            self.outcome,
            self.instance_state,
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
            or self.instance_state != RETRIEVED_STATE
            or not self.knowledge_retrieved
            or any(later)
            or not 0 <= self.result_count <= 20
            or not 20 <= len(self.purpose.strip()) <= 1_000
            or self.retrieved_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.retrieved_at < self.expires_at
            or not _digests(
                self.publication_digest,
                self.consumer_subject_digest,
                self.browser_session_binding_digest,
                self.retrieval_policy_digest,
                self.retrieval_receipt_digest,
                self.query_digest,
                self.authorization_context_digest,
                self.evidence_package_digest,
                self.protected_artifact_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge retrieval record is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeRetrievalResult:
    record: OperationalKnowledgeRetrievalRecord
    evidence: OperationalKnowledgeEvidencePackage
