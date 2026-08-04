from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_EVIDENCE = "needs_evidence"
    DEFERRED = "deferred"
    EXPIRED = "expired"


class ApprovalOutcome(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_EVIDENCE = "needs_evidence"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class ApprovalCreateRequest:
    recommendation_id: str
    recommendation_version: int
    target_id: str
    option_id: str
    purpose: str
    expires_in_minutes: int

    def __post_init__(self) -> None:
        if self.recommendation_version < 1:
            raise ValueError("recommendation version must be positive")
        if not all(
            value.strip()
            for value in (
                self.recommendation_id,
                self.target_id,
                self.option_id,
                self.purpose,
            )
        ):
            raise ValueError("approval request fields are required")
        if not 5 <= self.expires_in_minutes <= 240:
            raise ValueError("approval expiry must be between 5 and 240 minutes")


@dataclass(frozen=True, slots=True)
class ApprovalPlanStep:
    order: int
    step_id: str
    conceptual_action: str
    capability_id: str | None
    capability_class: str
    expected_output: str
    stop_condition: str


@dataclass(frozen=True, slots=True)
class ApprovalPacket:
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
    risk_rationales: tuple[str, ...]
    evidence_references: tuple[str, ...]
    evidence_summaries: tuple[str, ...]
    alternatives: tuple[str, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    affected_components: tuple[str, ...]
    possibly_affected_services: tuple[str, ...]
    blast_radius: str
    impact_confirmed: bool
    graph_maturity: str
    impact_gaps: tuple[str, ...]
    duration_minimum_minutes: int
    duration_maximum_minutes: int
    duration_basis: str
    interruption_expected_mode: str
    interruption_worst_credible_mode: str
    interruption_expected_minutes: tuple[int, int]
    interruption_worst_credible_minutes: tuple[int, int]
    interruption_unknowns: tuple[str, ...]
    plan_steps: tuple[ApprovalPlanStep, ...]
    preconditions: tuple[str, ...]
    success_criteria: tuple[str, ...]
    verification_criteria: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    recovery_strategy: str
    rollback_feasible: bool
    recovery_duration_minimum_minutes: int
    recovery_duration_maximum_minutes: int
    recovery_gaps: tuple[str, ...]
    policy_constraints: tuple[str, ...]
    execution_authorized: bool

    def __post_init__(self) -> None:
        if self.packet_version < 1 or self.recommendation_version < 1 or self.option_version < 1:
            raise ValueError("approval source versions must be positive")
        if any(value.tzinfo is None for value in (self.created_at, self.expires_at)):
            raise ValueError("approval timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("approval expiry must follow creation")
        if len(self.canonical_digest) != 64:
            raise ValueError("approval packet requires a SHA-256 digest")
        if self.execution_authorized:
            raise ValueError("approval packets cannot authorize execution")


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    decision_id: str
    request_version: int
    outcome: ApprovalOutcome
    reviewer_id: str
    decided_at: datetime
    rationale: str

    def __post_init__(self) -> None:
        if self.request_version < 1 or self.decided_at.tzinfo is None:
            raise ValueError("approval decision version and time are required")
        if not self.rationale.strip():
            raise ValueError("approval decisions require a rationale")


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    request_id: str
    version: int
    state: ApprovalState
    packet: ApprovalPacket
    created_at: datetime
    updated_at: datetime
    decisions: tuple[ApprovalDecision, ...]
    execution_authorized: bool

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("approval request version must be positive")
        if any(value.tzinfo is None for value in (self.created_at, self.updated_at)):
            raise ValueError("approval record timestamps must be timezone-aware")
        if self.execution_authorized:
            raise ValueError("approval records cannot authorize execution")
