from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationManifest,
    ProtectedDraftAdjudicationRecord,
    ProtectedDraftAdjudicationResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ProtectedDraftAdjudicationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.protected-draft-adjudication-input.v1", pattern=STABLE_ID
    )
    invocation_digest: str = Field(pattern=DIGEST)
    adjudication_policy_id: str = Field(pattern=STABLE_ID)
    adjudication_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_draft_is_untrusted: bool
    acknowledged_no_content_presentation: bool
    acknowledged_no_answer_or_operational_authority: bool


class ProtectedDraftAdjudicationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adjudication_id: str
    schema_version: str
    version: int
    invocation_id: str
    invocation_digest: str
    context_id: str
    context_digest: str
    organization_id: str
    environment_id: str
    classification: str
    adjudication_policy_id: str
    adjudication_policy_digest: str
    adjudication_policy_version: str
    adjudicator_id: str
    adjudication_receipt_digest: str
    draft_digest: str
    report_digest: str
    check_set_digest: str
    citation_coverage_digest: str
    unknown_preservation_digest: str
    prohibited_output_digest: str
    check_count: int
    citation_count: int
    unknown_count: int
    outcome: str
    adjudicated_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_retrieved: bool
    model_context_available: bool
    model_invoked: bool
    protected_draft_available: bool
    model_draft_adjudicated: bool
    answer_generated: bool
    graph_updated: bool
    scheduled: bool
    workflow_continued: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ProtectedDraftAdjudicationRecord
    ) -> ProtectedDraftAdjudicationData:
        return cls.model_validate(record, from_attributes=True)


class ProtectedDraftAdjudicationManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adjudication_id: str
    invocation_id: str
    context_id: str
    outcome: str
    check_count: int
    citation_count: int
    unknown_count: int
    report_digest: str
    check_set_digest: str
    citation_coverage_digest: str
    unknown_preservation_digest: str
    prohibited_output_digest: str
    adjudicated_at: datetime
    expires_at: datetime

    @classmethod
    def from_domain(
        cls, manifest: ProtectedDraftAdjudicationManifest
    ) -> ProtectedDraftAdjudicationManifestData:
        return cls.model_validate(manifest, from_attributes=True)


class ProtectedDraftAdjudicationResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adjudication: ProtectedDraftAdjudicationData
    manifest: ProtectedDraftAdjudicationManifestData

    @classmethod
    def from_domain(
        cls, result: ProtectedDraftAdjudicationResult
    ) -> ProtectedDraftAdjudicationResultData:
        return cls(
            adjudication=ProtectedDraftAdjudicationData.from_domain(result.record),
            manifest=ProtectedDraftAdjudicationManifestData.from_domain(result.manifest),
        )


class ProtectedDraftAdjudicationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ProtectedDraftAdjudicationResultData
    meta: ResponseMeta
