from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.investigations.domain.models import EvidenceUnit


class RecommendationCategory(StrEnum):
    INVESTIGATE = "investigate"
    ESCALATE = "escalate"
    DEFER_NO_ACTION = "defer_no_action"
    RESTORATION_PLANNING = "restoration_planning"
    REMEDIATION_PLANNING = "remediation_planning"


class OptionState(StrEnum):
    VIABLE = "viable"
    BLOCKED = "blocked"


class PreferenceState(StrEnum):
    PREFERRED = "preferred"
    ALTERNATIVE = "alternative"
    INELIGIBLE = "ineligible"


class RiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class RecommendationState(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


@dataclass(frozen=True, slots=True)
class RecommendationRequest:
    source_case_id: str
    source_case_version: int
    target_id: str
    decision_question: str
    accountable_audience: str
    horizon: str
    constraints: tuple[str, ...]
    maximum_capability_class: str
    max_options: int

    def __post_init__(self) -> None:
        if self.source_case_version < 1:
            raise ValueError("source RCA version must be positive")
        if not all(
            value.strip()
            for value in (
                self.source_case_id,
                self.target_id,
                self.decision_question,
                self.accountable_audience,
                self.horizon,
            )
        ):
            raise ValueError("recommendation request fields are required")
        if self.maximum_capability_class not in {"C0", "C1"}:
            raise ValueError("this slice is limited to C0 and C1 viable options")
        if not 3 <= self.max_options <= 5:
            raise ValueError("recommendation option budget must be between 3 and 5")


@dataclass(frozen=True, slots=True)
class Applicability:
    products: tuple[str, ...]
    versions: tuple[str, ...]
    environments: tuple[str, ...]
    targets: tuple[str, ...]
    services: tuple[str, ...]
    valid_from: datetime
    valid_until: datetime
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.valid_from.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("applicability timestamps must be timezone-aware")
        if self.valid_until <= self.valid_from:
            raise ValueError("applicability window must be increasing")


@dataclass(frozen=True, slots=True)
class PlanStep:
    step_id: str
    order: int
    phase: str
    conceptual_action: str
    capability_id: str | None
    capability_class: str
    expected_output: str
    stop_condition: str
    executable_by_atlas: bool

    def __post_init__(self) -> None:
        if self.order < 1 or self.capability_class not in {"C0", "C1", "C2", "C3", "C4", "C5"}:
            raise ValueError("invalid recommendation plan step")
        if self.executable_by_atlas:
            raise ValueError("this slice cannot contain executable recommendation steps")


@dataclass(frozen=True, slots=True)
class DurationEstimate:
    minimum_minutes: int
    maximum_minutes: int
    basis: str
    confidence: str

    def __post_init__(self) -> None:
        if self.minimum_minutes < 0 or self.maximum_minutes < self.minimum_minutes:
            raise ValueError("invalid duration estimate")


@dataclass(frozen=True, slots=True)
class InterruptionEstimate:
    expected_mode: str
    worst_credible_mode: str
    expected_minutes: tuple[int, int]
    worst_credible_minutes: tuple[int, int]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RiskDimension:
    dimension: str
    level: RiskLevel
    rationale: str


@dataclass(frozen=True, slots=True)
class ImpactSummary:
    affected_components: tuple[str, ...]
    possibly_affected_services: tuple[str, ...]
    explicitly_unaffected_entities: tuple[str, ...]
    blast_radius: str
    redundancy_effect: str
    data_protection_effect: str
    impact_confirmed: bool
    graph_maturity: str
    gaps: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.impact_confirmed:
            raise ValueError("this slice cannot confirm recommendation impact")


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    strategy: str
    rollback_feasible: bool
    point_of_no_return: str
    trigger_conditions: tuple[str, ...]
    estimated_duration: DurationEstimate
    data_implications: str
    gaps: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GovernanceRequirements:
    required_roles: tuple[str, ...]
    policy_references: tuple[str, ...]
    approval_required: bool
    itsm_record_required: bool
    vendor_support_required: bool
    human_handoff: str


@dataclass(frozen=True, slots=True)
class RecommendationOption:
    option_id: str
    version: int
    category: RecommendationCategory
    state: OptionState
    preference: PreferenceState
    title: str
    intended_outcome: str
    applicability: Applicability
    plan_steps: tuple[PlanStep, ...]
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    confidence: str
    confidence_rationale: str
    risk_dimensions: tuple[RiskDimension, ...]
    overall_risk: RiskLevel
    impact: ImpactSummary
    duration: DurationEstimate
    interruption: InterruptionEstimate
    preconditions: tuple[str, ...]
    success_criteria: tuple[str, ...]
    verification_criteria: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    recovery: RecoveryPlan
    governance: GovernanceRequirements
    residual_risk: tuple[str, ...]
    policy_outcome: str
    exclusion_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version < 1 or not self.plan_steps:
            raise ValueError("recommendation options require a version and plan")
        orders = [step.order for step in self.plan_steps]
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("recommendation plan steps must have contiguous order")
        if self.state is OptionState.BLOCKED and not self.exclusion_reasons:
            raise ValueError("blocked options require exclusion reasons")
        if self.state is OptionState.VIABLE and self.exclusion_reasons:
            raise ValueError("viable options cannot contain exclusion reasons")
        if self.preference is PreferenceState.PREFERRED and self.state is not OptionState.VIABLE:
            raise ValueError("only viable options can be preferred")


@dataclass(frozen=True, slots=True)
class ComparisonDimension:
    dimension: str
    precedence: int
    option_values: tuple[tuple[str, str], ...]
    rationale: str


@dataclass(frozen=True, slots=True)
class HumanReview:
    status: ReviewStatus
    reviewer_id: str | None
    reviewed_at: datetime | None
    rationale: str | None

    def __post_init__(self) -> None:
        if self.status is ReviewStatus.PENDING and any(
            value is not None for value in (self.reviewer_id, self.reviewed_at, self.rationale)
        ):
            raise ValueError("pending recommendation review cannot contain a decision")


@dataclass(frozen=True, slots=True)
class RecommendationArtifact:
    recommendation_id: str
    version: int
    prior_version_id: str | None
    owner: str
    state: RecommendationState
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
    constraints: tuple[str, ...]
    source_case_id: str
    source_case_version: int
    source_case_state: str
    source_evidence: tuple[EvidenceUnit, ...]
    options: tuple[RecommendationOption, ...]
    comparisons: tuple[ComparisonDimension, ...]
    preferred_option_id: str | None
    preference_rationale: str
    policy_constraints: tuple[str, ...]
    excluded_option_ids: tuple[str, ...]
    human_review: HumanReview
    component_versions: tuple[str, ...]
    data_profile: str
    execution_authorized: bool
    safety_notice: str

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("recommendation version must be positive")
        if any(value.tzinfo is None for value in (self.created_at, self.expires_at)):
            raise ValueError("recommendation timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("recommendation expiry must follow creation")
        if self.execution_authorized:
            raise ValueError("recommendations cannot authorize execution")
        option_ids = {option.option_id for option in self.options}
        if len(option_ids) != len(self.options):
            raise ValueError("recommendation option IDs must be unique")
        if self.preferred_option_id is not None:
            preferred = [
                option
                for option in self.options
                if option.option_id == self.preferred_option_id
                and option.preference is PreferenceState.PREFERRED
                and option.state is OptionState.VIABLE
            ]
            if len(preferred) != 1:
                raise ValueError("preferred option must resolve to one viable option")
        evidence_ids = {item.evidence_id for item in self.source_evidence}
        references = {
            reference
            for option in self.options
            for reference in option.supporting_evidence + option.contradicting_evidence
        }
        if not references <= evidence_ids:
            raise ValueError("recommendation contains unresolved evidence references")
