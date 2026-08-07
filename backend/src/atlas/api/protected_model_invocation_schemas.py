from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.ai.domain.protected_model_invocation import (
    ProtectedModelInvocationManifest,
    ProtectedModelInvocationRecord,
    ProtectedModelInvocationResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ProtectedModelInvocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.protected-model-invocation-input.v1", pattern=STABLE_ID
    )
    context_digest: str = Field(pattern=DIGEST)
    invocation_policy_id: str = Field(pattern=STABLE_ID)
    invocation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_draft_is_untrusted: bool
    acknowledged_citations_and_unknowns_require_validation: bool
    acknowledged_no_answer_or_operational_authority: bool


class ProtectedModelInvocationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invocation_id: str
    schema_version: str
    version: int
    context_id: str
    context_digest: str
    organization_id: str
    environment_id: str
    classification: str
    invocation_policy_id: str
    invocation_policy_digest: str
    invocation_policy_version: str
    gateway_id: str
    invocation_receipt_digest: str
    endpoint_profile_id: str
    endpoint_profile_digest: str
    model_id: str
    task_class: str
    response_schema_version: str
    draft_digest: str
    citation_set_digest: str
    output_safety_digest: str
    input_tokens: int
    output_tokens: int
    maximum_output_tokens: int
    finish_reason: str
    outcome: str
    invoked_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_retrieved: bool
    model_context_available: bool
    model_invoked: bool
    protected_draft_available: bool
    answer_generated: bool
    graph_updated: bool
    scheduled: bool
    workflow_continued: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, record: ProtectedModelInvocationRecord) -> ProtectedModelInvocationData:
        return cls.model_validate(record, from_attributes=True)


class ProtectedModelInvocationManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invocation_id: str
    context_id: str
    endpoint_profile_id: str
    model_id: str
    task_class: str
    response_schema_version: str
    citation_count: int
    unknown_count: int
    input_tokens: int
    output_tokens: int
    maximum_output_tokens: int
    finish_reason: str
    outcome: str
    draft_digest: str
    citation_set_digest: str
    output_safety_digest: str
    invoked_at: datetime
    expires_at: datetime

    @classmethod
    def from_domain(
        cls, manifest: ProtectedModelInvocationManifest
    ) -> ProtectedModelInvocationManifestData:
        return cls.model_validate(manifest, from_attributes=True)


class ProtectedModelInvocationResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invocation: ProtectedModelInvocationData
    manifest: ProtectedModelInvocationManifestData

    @classmethod
    def from_domain(
        cls, result: ProtectedModelInvocationResult
    ) -> ProtectedModelInvocationResultData:
        return cls(
            invocation=ProtectedModelInvocationData.from_domain(result.record),
            manifest=ProtectedModelInvocationManifestData.from_domain(result.manifest),
        )


class ProtectedModelInvocationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ProtectedModelInvocationResultData
    meta: ResponseMeta
