from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.approvals.domain.models import ApprovalRecord


class ApprovalCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str = Field(min_length=1, max_length=120)
    recommendation_version: int = Field(ge=1)
    option_id: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=5, max_length=500)
    expires_in_minutes: int = Field(default=60, ge=5, le=240)


class ApprovalDecisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: str = Field(pattern="^(approve|reject|needs_evidence|defer)$")
    rationale: str = Field(min_length=5, max_length=1000)
    expected_version: int = Field(ge=1)


class ApprovalPlanStepData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: int
    step_id: str
    conceptual_action: str
    capability_id: str | None
    capability_class: str
    expected_output: str
    stop_condition: str


class ApprovalPacketData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    packet_version: int
    canonicalization_version: str
    canonical_digest: str
    requested_by: str
    purpose: str
    created_at: datetime
    expires_at: datetime
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    recommendation_id: str
    recommendation_version: int
    source_case_id: str
    source_case_version: int
    option_id: str
    option_version: int
    option_title: str
    option_category: str
    option_confidence: str
    confidence_rationale: str
    overall_risk: str
    risk_rationales: list[str]
    evidence_references: list[str]
    evidence_summaries: list[str]
    alternatives: list[str]
    assumptions: list[str]
    unknowns: list[str]
    affected_components: list[str]
    possibly_affected_services: list[str]
    blast_radius: str
    impact_confirmed: bool
    graph_maturity: str
    impact_gaps: list[str]
    duration_minimum_minutes: int
    duration_maximum_minutes: int
    duration_basis: str
    interruption_expected_mode: str
    interruption_worst_credible_mode: str
    interruption_expected_minutes: tuple[int, int]
    interruption_worst_credible_minutes: tuple[int, int]
    interruption_unknowns: list[str]
    plan_steps: list[ApprovalPlanStepData]
    preconditions: list[str]
    success_criteria: list[str]
    verification_criteria: list[str]
    stop_conditions: list[str]
    recovery_strategy: str
    rollback_feasible: bool
    recovery_duration_minimum_minutes: int
    recovery_duration_maximum_minutes: int
    recovery_gaps: list[str]
    policy_constraints: list[str]
    execution_authorized: bool


class ApprovalDecisionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    request_version: int
    outcome: str
    reviewer_id: str
    decided_at: datetime
    rationale: str


class ApprovalRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    version: int
    state: str
    packet: ApprovalPacketData
    created_at: datetime
    updated_at: datetime
    decisions: list[ApprovalDecisionData]
    execution_authorized: bool

    @classmethod
    def from_domain(cls, record: ApprovalRecord) -> Self:
        return cls.model_validate(record, from_attributes=True)


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ApprovalRecordData
    meta: ResponseMeta
