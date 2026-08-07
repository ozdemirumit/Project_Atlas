from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.model_context_assembly import (
    ProtectedModelContextManifest,
    ProtectedModelContextRecord,
    ProtectedModelContextResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ProtectedModelContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="atlas.protected-model-context-input.v1", pattern=STABLE_ID)
    retrieval_digest: str = Field(pattern=DIGEST)
    context_policy_id: str = Field(pattern=STABLE_ID)
    context_policy_digest: str = Field(pattern=DIGEST)
    objective: str = Field(min_length=3, max_length=4000)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_untrusted_intent: bool
    acknowledged_citation_boundaries: bool
    acknowledged_no_model_or_operational_authority: bool


class ProtectedModelContextData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str
    schema_version: str
    version: int
    retrieval_id: str
    retrieval_digest: str
    publication_id: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    context_policy_id: str
    context_policy_digest: str
    context_policy_version: str
    assembler_id: str
    assembly_receipt_digest: str
    objective_digest: str
    context_package_digest: str
    evidence_set_digest: str
    citation_set_digest: str
    safety_validation_digest: str
    budget_allocation_digest: str
    destination_profile_digest: str
    task_class: str
    output_schema_version: str
    included_evidence_count: int
    character_count: int
    estimated_token_count: int
    maximum_context_characters: int
    maximum_estimated_tokens: int
    outcome: str
    assembled_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_retrieved: bool
    model_context_available: bool
    model_invoked: bool
    answer_generated: bool
    graph_updated: bool
    scheduled: bool
    workflow_continued: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, record: ProtectedModelContextRecord) -> ProtectedModelContextData:
        return cls.model_validate(record, from_attributes=True)


class ProtectedModelContextManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str
    retrieval_id: str
    task_class: str
    output_schema_version: str
    classification: str
    included_evidence_count: int
    character_count: int
    estimated_token_count: int
    maximum_context_characters: int
    maximum_estimated_tokens: int
    outcome: str
    evidence_set_digest: str
    citation_set_digest: str
    safety_validation_digest: str
    context_package_digest: str
    assembled_at: datetime
    expires_at: datetime

    @classmethod
    def from_domain(
        cls, manifest: ProtectedModelContextManifest
    ) -> ProtectedModelContextManifestData:
        return cls.model_validate(manifest, from_attributes=True)


class ProtectedModelContextResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: ProtectedModelContextData
    manifest: ProtectedModelContextManifestData

    @classmethod
    def from_domain(cls, result: ProtectedModelContextResult) -> ProtectedModelContextResultData:
        return cls(
            context=ProtectedModelContextData.from_domain(result.record),
            manifest=ProtectedModelContextManifestData.from_domain(result.manifest),
        )


class ProtectedModelContextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ProtectedModelContextResultData
    meta: ResponseMeta
