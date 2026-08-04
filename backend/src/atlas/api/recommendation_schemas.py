from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.investigation_schemas import EvidenceUnitData
from atlas.api.schemas import ResponseMeta
from atlas.modules.recommendations.domain.models import RecommendationArtifact


class RecommendationCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_case_id: str = Field(min_length=1, max_length=120)
    source_case_version: int = Field(ge=1)
    decision_question: str = Field(min_length=1, max_length=500)
    accountable_audience: str = Field(min_length=1, max_length=160)
    horizon: str = Field(min_length=1, max_length=80)
    constraints: list[str] = Field(default_factory=list, max_length=12)
    maximum_capability_class: str = Field(default="C1", pattern="^C[01]$")
    max_options: int = Field(default=5, ge=3, le=5)


class ApplicabilityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    products: list[str]
    versions: list[str]
    environments: list[str]
    targets: list[str]
    services: list[str]
    valid_from: datetime
    valid_until: datetime
    limitations: list[str]


class PlanStepData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    order: int
    phase: str
    conceptual_action: str
    capability_id: str | None
    capability_class: str
    expected_output: str
    stop_condition: str
    executable_by_atlas: bool


class DurationEstimateData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_minutes: int
    maximum_minutes: int
    basis: str
    confidence: str


class InterruptionEstimateData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_mode: str
    worst_credible_mode: str
    expected_minutes: tuple[int, int]
    worst_credible_minutes: tuple[int, int]
    assumptions: list[str]
    unknowns: list[str]


class RiskDimensionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str
    level: str
    rationale: str


class ImpactSummaryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affected_components: list[str]
    possibly_affected_services: list[str]
    explicitly_unaffected_entities: list[str]
    blast_radius: str
    redundancy_effect: str
    data_protection_effect: str
    impact_confirmed: bool
    graph_maturity: str
    gaps: list[str]


class RecoveryPlanData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str
    rollback_feasible: bool
    point_of_no_return: str
    trigger_conditions: list[str]
    estimated_duration: DurationEstimateData
    data_implications: str
    gaps: list[str]


class GovernanceRequirementsData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_roles: list[str]
    policy_references: list[str]
    approval_required: bool
    itsm_record_required: bool
    vendor_support_required: bool
    human_handoff: str


class RecommendationOptionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str
    version: int
    category: str
    state: str
    preference: str
    title: str
    intended_outcome: str
    applicability: ApplicabilityData
    plan_steps: list[PlanStepData]
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    assumptions: list[str]
    unknowns: list[str]
    confidence: str
    confidence_rationale: str
    risk_dimensions: list[RiskDimensionData]
    overall_risk: str
    impact: ImpactSummaryData
    duration: DurationEstimateData
    interruption: InterruptionEstimateData
    preconditions: list[str]
    success_criteria: list[str]
    verification_criteria: list[str]
    stop_conditions: list[str]
    recovery: RecoveryPlanData
    governance: GovernanceRequirementsData
    residual_risk: list[str]
    policy_outcome: str
    exclusion_reasons: list[str]


class ComparisonDimensionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str
    precedence: int
    option_values: list[tuple[str, str]]
    rationale: str


class RecommendationReviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    reviewer_id: str | None
    reviewed_at: datetime | None
    rationale: str | None


class RecommendationArtifactData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    version: int
    prior_version_id: str | None
    owner: str
    state: str
    requested_by: str
    created_at: datetime
    expires_at: datetime
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    decision_question: str
    accountable_audience: str
    horizon: str
    constraints: list[str]
    source_case_id: str
    source_case_version: int
    source_case_state: str
    source_evidence: list[EvidenceUnitData]
    options: list[RecommendationOptionData]
    comparisons: list[ComparisonDimensionData]
    preferred_option_id: str | None
    preference_rationale: str
    policy_constraints: list[str]
    excluded_option_ids: list[str]
    human_review: RecommendationReviewData
    component_versions: list[str]
    data_profile: str
    execution_authorized: bool
    safety_notice: str

    @classmethod
    def from_domain(cls, artifact: RecommendationArtifact) -> RecommendationArtifactData:
        return cls.model_validate(artifact, from_attributes=True)


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: RecommendationArtifactData
    meta: ResponseMeta
