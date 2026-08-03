from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.api.investigation_schemas import EvidenceUnitData, TimelineEventData
from atlas.api.schemas import ResponseMeta
from atlas.modules.rca.domain.models import RcaCase


class RcaCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str = Field(min_length=1, max_length=120)
    user_report: str = Field(min_length=1, max_length=1000)
    expected_behavior: str = Field(min_length=1, max_length=500)
    actual_behavior: str = Field(min_length=1, max_length=500)
    window_start: datetime
    window_end: datetime
    max_evidence_records: int = Field(default=12, ge=1, le=20)

    @model_validator(mode="after")
    def validate_window(self) -> RcaCreatePayload:
        if self.window_start.tzinfo is None or self.window_end.tzinfo is None:
            raise ValueError("RCA time window must be timezone-aware")
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        return self


class IncidentReferenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_type: str
    reference_id: str
    authority: str


class SymptomData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symptom_id: str
    statement: str
    first_observed_at: datetime
    current_state: str
    evidence_references: list[str]


class ImpactScopeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affected_entities: list[str]
    possibly_affected_services: list[str]
    explicitly_unaffected_entities: list[str]
    current_impact: str
    business_criticality: str
    impact_confirmed: bool
    limitations: list[str]


class DiagnosticStepData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    question: str
    target_id: str
    scope: str
    capability_id: str
    capability_class: str
    evidence_source: str
    preconditions: list[str]
    expected_duration_seconds: int
    expected_load: str
    max_output_records: int
    expected_if_supported: str
    expected_if_not_supported: str
    timeout_seconds: int
    stop_condition: str
    required_role: str
    policy_reference: str
    approval_required: bool
    classification: str
    retention: str
    supported_branch: str
    unsupported_branch: str


class RcaHypothesisData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    rank: int
    fault_family: str
    cause_type: str
    statement: str
    mechanism: str
    expected_affected_entities: list[str]
    expected_unaffected_entities: list[str]
    expected_sequence: list[str]
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    missing_expected_observations: list[str]
    confounders: list[str]
    assumptions: list[str]
    confirmation_level: str
    confidence_rationale: str
    diagnostic_steps: list[DiagnosticStepData]


class RcaFindingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    cause_type: str
    statement: str
    confirmation_level: str
    evidence_references: list[str]
    residual_uncertainty: list[str]


class ProvisionalCauseStatementData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str
    confirmation_level: str
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    residual_uncertainty: list[str]
    alternatives_not_ruled_out: list[str]
    prevention_or_verification_implication: str


class HumanReviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    reviewer_id: str | None
    reviewed_at: datetime | None
    decision_reason: str | None
    domain_confirmation_criterion: str | None


class RcaCaseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    version: int
    prior_version_id: str | None
    owner: str
    requested_by: str
    state: str
    severity: str
    created_at: datetime
    updated_at: datetime
    incident_references: list[IncidentReferenceData]
    user_report: str
    expected_behavior: str
    actual_behavior: str
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    window_start: datetime
    window_end: datetime
    fault_families: list[str]
    symptoms: list[SymptomData]
    impact_scope: ImpactScopeData
    source_investigation_artifact_id: str
    source_investigation_version: int
    evidence: list[EvidenceUnitData]
    timeline: list[TimelineEventData]
    hypotheses: list[RcaHypothesisData]
    findings: list[RcaFindingData]
    assumptions: list[str]
    unknowns: list[str]
    conflicts: list[str]
    evidence_gaps: list[str]
    blocker: str
    safest_next_step: str
    provisional_statement: ProvisionalCauseStatementData
    human_review: HumanReviewData
    component_versions: list[str]
    data_profile: str
    root_cause_confirmed: bool
    safety_notice: str

    @classmethod
    def from_domain(cls, case: RcaCase) -> RcaCaseData:
        return cls.model_validate(case, from_attributes=True)


class RcaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: RcaCaseData
    meta: ResponseMeta
