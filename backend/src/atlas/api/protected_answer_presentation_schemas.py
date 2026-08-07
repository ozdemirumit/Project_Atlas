from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.ai.domain.protected_answer_presentation import (
    ProtectedAnswerPresentationManifest,
    ProtectedAnswerPresentationRecord,
    ProtectedAnswerPresentationResult,
    ProtectedPresentedAnswer,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ProtectedAnswerPresentationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.protected-answer-presentation-input.v1", pattern=STABLE_ID
    )
    adjudication_digest: str = Field(pattern=DIGEST)
    presentation_policy_id: str = Field(pattern=STABLE_ID)
    presentation_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_bounded_decision_support: bool
    acknowledged_citations_and_unknowns_are_material: bool
    acknowledged_no_recommendation_or_operational_authority: bool


class ProtectedAnswerPresentationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation_id: str
    schema_version: str
    version: int
    adjudication_id: str
    adjudication_digest: str
    invocation_id: str
    invocation_digest: str
    context_id: str
    context_digest: str
    organization_id: str
    environment_id: str
    classification: str
    presentation_policy_id: str
    presentation_policy_digest: str
    presentation_policy_version: str
    presenter_id: str
    presentation_receipt_digest: str
    draft_digest: str
    report_digest: str
    answer_digest: str
    citation_set_digest: str
    unknown_set_digest: str
    source_binding_digest: str
    rendering_digest: str
    cleanup_digest: str
    summary_character_count: int
    citation_count: int
    unknown_count: int
    byte_count: int
    media_type: str
    presented_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_retrieved: bool
    model_context_available: bool
    model_invoked: bool
    protected_draft_available: bool
    model_draft_adjudicated: bool
    answer_presented: bool
    recommendation_generated: bool
    graph_updated: bool
    scheduled: bool
    workflow_continued: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ProtectedAnswerPresentationRecord
    ) -> ProtectedAnswerPresentationData:
        return cls.model_validate(record, from_attributes=True)


class ProtectedPresentedAnswerData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation_id: str
    summary: str
    citation_references: tuple[str, ...]
    unknowns: tuple[str, ...]
    media_type: str
    byte_count: int
    generated_at: datetime
    expires_at: datetime
    canonical_digest: str

    @classmethod
    def from_domain(cls, answer: ProtectedPresentedAnswer) -> ProtectedPresentedAnswerData:
        return cls.model_validate(answer, from_attributes=True)


class ProtectedAnswerPresentationManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation_id: str
    adjudication_id: str
    invocation_id: str
    context_id: str
    summary_character_count: int
    citation_count: int
    unknown_count: int
    byte_count: int
    media_type: str
    answer_digest: str
    citation_set_digest: str
    unknown_set_digest: str
    source_binding_digest: str
    rendering_digest: str
    cleanup_digest: str
    presented_at: datetime
    expires_at: datetime

    @classmethod
    def from_domain(
        cls, manifest: ProtectedAnswerPresentationManifest
    ) -> ProtectedAnswerPresentationManifestData:
        return cls.model_validate(manifest, from_attributes=True)


class ProtectedAnswerPresentationResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation: ProtectedAnswerPresentationData
    manifest: ProtectedAnswerPresentationManifestData
    answer: ProtectedPresentedAnswerData

    @classmethod
    def from_domain(
        cls, result: ProtectedAnswerPresentationResult
    ) -> ProtectedAnswerPresentationResultData:
        return cls(
            presentation=ProtectedAnswerPresentationData.from_domain(result.record),
            manifest=ProtectedAnswerPresentationManifestData.from_domain(result.manifest),
            answer=ProtectedPresentedAnswerData.from_domain(result.answer),
        )


class ProtectedAnswerPresentationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ProtectedAnswerPresentationResultData
    meta: ResponseMeta
