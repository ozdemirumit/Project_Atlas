from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.api.schemas import ResponseMeta
from atlas.modules.investigations.domain.models import ReasoningArtifact


class InvestigationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)
    intended_decision: str = Field(min_length=1, max_length=240)
    window_start: datetime
    window_end: datetime
    max_evidence_records: int = Field(default=12, ge=1, le=20)

    @model_validator(mode="after")
    def validate_window(self) -> InvestigationCreateRequest:
        if self.window_start.tzinfo is None or self.window_end.tzinfo is None:
            raise ValueError("investigation time window must be timezone-aware")
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        return self


class EvidenceUnitData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    artifact_version: str
    source_type: str
    source_system: str
    source_version: str
    target_id: str
    observed_at: datetime
    applicable_from: datetime
    applicable_to: datetime | None
    freshness: str
    classification: str
    authorization_reference: str
    collection_method: str
    summary: str
    integrity: str
    completeness: str
    quality_limitations: list[str]
    citation: str


class TimelineEventData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    summary: str
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    evidence_references: list[str]
    clock_quality: str


class ClaimData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    epistemic_type: str
    text: str
    scope: str
    window_start: datetime
    window_end: datetime
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    assumptions: list[str]
    confidence: str
    supporting_factors: list[str]
    limiting_factors: list[str]
    validation_state: str


class DiscriminatingCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    title: str
    rationale: str
    capability_id: str
    capability_class: str
    target_id: str
    expected_if_supported: str
    expected_if_not_supported: str
    timeout_seconds: int
    stop_condition: str


class HypothesisData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    statement: str
    state: str
    expected_consequences: list[str]
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    assumptions: list[str]
    confidence: str
    confidence_rationale: str
    limiting_factors: list[str]
    discriminating_checks: list[DiscriminatingCheckData]


class ReasoningSummaryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    known: list[str]
    inferred: list[str]
    alternatives: list[str]
    unknowns: list[str]
    confidence: str
    confidence_rationale: str
    safest_next_check: str
    supported_decision: str
    unsupported_decision: str


class ReasoningArtifactData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    version: int
    prior_version_id: str | None
    requested_by: str
    created_at: datetime
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    question: str
    intended_decision: str
    window_start: datetime
    window_end: datetime
    evidence: list[EvidenceUnitData]
    timeline: list[TimelineEventData]
    claims: list[ClaimData]
    hypotheses: list[HypothesisData]
    assumptions: list[str]
    unknowns: list[str]
    conflicts: list[str]
    excluded_evidence: list[str]
    stop_reason: str
    recommended_next_evidence: list[str]
    component_versions: list[str]
    summary: ReasoningSummaryData
    data_profile: str
    root_cause_confirmed: bool
    outage_confirmed: bool
    safety_notice: str

    @classmethod
    def from_domain(cls, artifact: ReasoningArtifact) -> ReasoningArtifactData:
        return cls.model_validate(artifact, from_attributes=True)


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ReasoningArtifactData
    meta: ResponseMeta
