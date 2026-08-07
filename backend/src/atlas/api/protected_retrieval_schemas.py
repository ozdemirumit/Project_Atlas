from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.protected_retrieval import (
    OperationalKnowledgeEvidencePackage,
    OperationalKnowledgeEvidenceResult,
    OperationalKnowledgeRetrievalRecord,
    OperationalKnowledgeRetrievalResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeRetrievalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-retrieval-input.v1", pattern=STABLE_ID
    )
    publication_digest: str = Field(pattern=DIGEST)
    retrieval_policy_id: str = Field(pattern=STABLE_ID)
    retrieval_policy_digest: str = Field(pattern=DIGEST)
    query: str = Field(min_length=3, max_length=4000)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_untrusted_evidence: bool
    acknowledged_unsafe_instructions: bool
    acknowledged_no_model_or_operational_authority: bool


class OperationalKnowledgeEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

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

    @classmethod
    def from_domain(
        cls, evidence: OperationalKnowledgeEvidenceResult
    ) -> OperationalKnowledgeEvidenceData:
        return cls.model_validate(evidence, from_attributes=True)


class OperationalKnowledgeEvidencePackageData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    results: tuple[OperationalKnowledgeEvidenceData, ...]
    outcome: str
    generated_at: datetime
    expires_at: datetime
    canonical_digest: str

    @classmethod
    def from_domain(
        cls, package: OperationalKnowledgeEvidencePackage
    ) -> OperationalKnowledgeEvidencePackageData:
        return cls(
            query=package.query,
            results=tuple(
                OperationalKnowledgeEvidenceData.from_domain(item) for item in package.results
            ),
            outcome=package.outcome,
            generated_at=package.generated_at,
            expires_at=package.expires_at,
            canonical_digest=package.canonical_digest,
        )


class OperationalKnowledgeRetrievalData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval_id: str
    schema_version: str
    version: int
    publication_id: str
    publication_digest: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    retrieval_policy_id: str
    retrieval_policy_digest: str
    retrieval_policy_version: str
    retriever_id: str
    retrieval_receipt_digest: str
    query_digest: str
    authorization_context_digest: str
    evidence_package_digest: str
    result_count: int
    outcome: str
    retrieved_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_retrieved: bool
    model_context_available: bool
    graph_updated: bool
    scheduled: bool
    workflow_continued: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: OperationalKnowledgeRetrievalRecord
    ) -> OperationalKnowledgeRetrievalData:
        return cls.model_validate(record, from_attributes=True)


class OperationalKnowledgeRetrievalResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval: OperationalKnowledgeRetrievalData
    evidence: OperationalKnowledgeEvidencePackageData

    @classmethod
    def from_domain(
        cls, result: OperationalKnowledgeRetrievalResult
    ) -> OperationalKnowledgeRetrievalResultData:
        return cls(
            retrieval=OperationalKnowledgeRetrievalData.from_domain(result.record),
            evidence=OperationalKnowledgeEvidencePackageData.from_domain(result.evidence),
        )


class OperationalKnowledgeRetrievalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeRetrievalResultData
    meta: ResponseMeta
