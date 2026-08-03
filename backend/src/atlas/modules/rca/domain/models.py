from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification
from atlas.modules.investigations.domain.models import EvidenceUnit, TimelineEvent


class RcaCaseState(StrEnum):
    PROVISIONAL = "provisional"
    INCONCLUSIVE = "inconclusive"
    REVIEWED = "reviewed"


class RcaSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CauseType(StrEnum):
    SYMPTOM = "symptom"
    TRIGGER = "trigger"
    ROOT_CAUSE = "root_cause"
    CONTRIBUTING_CAUSE = "contributing_cause"
    AMPLIFYING_FACTOR = "amplifying_factor"
    LATENT_CONDITION = "latent_condition"
    RECOVERY_FACTOR = "recovery_factor"
    OBSERVATION_FAILURE = "observation_failure"
    COINCIDENTAL_EVENT = "coincidental_event"


class ConfirmationLevel(StrEnum):
    SUSPECTED = "suspected"
    SUPPORTED = "supported"
    STRONGLY_SUPPORTED = "strongly_supported"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISPUTED = "disputed"
    CORRECTED = "corrected"


@dataclass(frozen=True, slots=True)
class RcaCreateRequest:
    incident_id: str
    target_id: str
    user_report: str
    expected_behavior: str
    actual_behavior: str
    window_start: datetime
    window_end: datetime
    max_evidence_records: int

    def __post_init__(self) -> None:
        if self.window_start.tzinfo is None or self.window_end.tzinfo is None:
            raise ValueError("RCA time window must be timezone-aware")
        if self.window_end <= self.window_start:
            raise ValueError("RCA time window must be increasing")
        if not all(
            value.strip()
            for value in (
                self.incident_id,
                self.target_id,
                self.user_report,
                self.expected_behavior,
                self.actual_behavior,
            )
        ):
            raise ValueError("RCA intake fields are required")
        if len(self.user_report) > 1000:
            raise ValueError("RCA user report must not exceed 1000 characters")
        if not 1 <= self.max_evidence_records <= 20:
            raise ValueError("RCA evidence budget must be between 1 and 20")


@dataclass(frozen=True, slots=True)
class IncidentReference:
    reference_type: str
    reference_id: str
    authority: str


@dataclass(frozen=True, slots=True)
class NormalizedSymptom:
    symptom_id: str
    statement: str
    first_observed_at: datetime
    current_state: str
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.first_observed_at.tzinfo is None:
            raise ValueError("symptom time must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("symptoms require evidence")


@dataclass(frozen=True, slots=True)
class ImpactScope:
    affected_entities: tuple[str, ...]
    possibly_affected_services: tuple[str, ...]
    explicitly_unaffected_entities: tuple[str, ...]
    current_impact: str
    business_criticality: str
    impact_confirmed: bool
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.impact_confirmed:
            raise ValueError("this RCA slice cannot confirm service impact")


@dataclass(frozen=True, slots=True)
class DiagnosticStep:
    step_id: str
    question: str
    target_id: str
    scope: str
    capability_id: str
    capability_class: str
    evidence_source: str
    preconditions: tuple[str, ...]
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
    classification: DataClassification
    retention: str
    supported_branch: str
    unsupported_branch: str

    def __post_init__(self) -> None:
        if self.capability_class not in {"C0", "C1"}:
            raise ValueError("RCA diagnostic steps are limited to C0 and C1")
        if min(self.expected_duration_seconds, self.max_output_records, self.timeout_seconds) < 1:
            raise ValueError("RCA diagnostic limits must be positive")
        if self.approval_required:
            raise ValueError("this slice contains only diagnostics that do not require approval")


@dataclass(frozen=True, slots=True)
class RcaHypothesis:
    hypothesis_id: str
    rank: int
    fault_family: str
    cause_type: CauseType
    statement: str
    mechanism: str
    expected_affected_entities: tuple[str, ...]
    expected_unaffected_entities: tuple[str, ...]
    expected_sequence: tuple[str, ...]
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]
    missing_expected_observations: tuple[str, ...]
    confounders: tuple[str, ...]
    assumptions: tuple[str, ...]
    confirmation_level: ConfirmationLevel
    confidence_rationale: str
    diagnostic_steps: tuple[DiagnosticStep, ...]

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("hypothesis rank must be positive")
        if not self.statement.strip() or not self.mechanism.strip():
            raise ValueError("RCA hypotheses require statement and mechanism")
        if not self.diagnostic_steps:
            raise ValueError("RCA hypotheses require diagnostic steps")


@dataclass(frozen=True, slots=True)
class RcaFinding:
    finding_id: str
    cause_type: CauseType
    statement: str
    confirmation_level: ConfirmationLevel
    evidence_references: tuple[str, ...]
    residual_uncertainty: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.cause_type is CauseType.ROOT_CAUSE:
            raise ValueError("this slice cannot produce a root-cause finding")
        if not self.evidence_references:
            raise ValueError("RCA findings require evidence")


@dataclass(frozen=True, slots=True)
class ProvisionalCauseStatement:
    statement: str
    confirmation_level: ConfirmationLevel
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]
    residual_uncertainty: tuple[str, ...]
    alternatives_not_ruled_out: tuple[str, ...]
    prevention_or_verification_implication: str

    def __post_init__(self) -> None:
        if self.confirmation_level is ConfirmationLevel.CONFIRMED:
            raise ValueError("a provisional statement cannot be confirmed")


@dataclass(frozen=True, slots=True)
class HumanReview:
    status: ReviewStatus
    reviewer_id: str | None
    reviewed_at: datetime | None
    decision_reason: str | None
    domain_confirmation_criterion: str | None

    def __post_init__(self) -> None:
        if self.status is ReviewStatus.PENDING and any(
            value is not None
            for value in (
                self.reviewer_id,
                self.reviewed_at,
                self.decision_reason,
                self.domain_confirmation_criterion,
            )
        ):
            raise ValueError("pending review cannot contain a review decision")
        if self.reviewed_at is not None and self.reviewed_at.tzinfo is None:
            raise ValueError("review time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RcaCase:
    case_id: str
    version: int
    prior_version_id: str | None
    owner: str
    requested_by: str
    state: RcaCaseState
    severity: RcaSeverity
    created_at: datetime
    updated_at: datetime
    incident_references: tuple[IncidentReference, ...]
    user_report: str
    expected_behavior: str
    actual_behavior: str
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    window_start: datetime
    window_end: datetime
    fault_families: tuple[str, ...]
    symptoms: tuple[NormalizedSymptom, ...]
    impact_scope: ImpactScope
    source_investigation_artifact_id: str
    source_investigation_version: int
    evidence: tuple[EvidenceUnit, ...]
    timeline: tuple[TimelineEvent, ...]
    hypotheses: tuple[RcaHypothesis, ...]
    findings: tuple[RcaFinding, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    conflicts: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    blocker: str
    safest_next_step: str
    provisional_statement: ProvisionalCauseStatement
    human_review: HumanReview
    component_versions: tuple[str, ...]
    data_profile: str
    root_cause_confirmed: bool
    safety_notice: str

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("RCA case version must be positive")
        if any(value.tzinfo is None for value in (self.created_at, self.updated_at)):
            raise ValueError("RCA case timestamps must be timezone-aware")
        if self.root_cause_confirmed and (
            self.human_review.status is not ReviewStatus.ACCEPTED
            or self.human_review.reviewer_id is None
            or self.human_review.domain_confirmation_criterion is None
        ):
            raise ValueError("confirmed RCA requires attributable review and domain criteria")
        if (
            any(
                hypothesis.confirmation_level is ConfirmationLevel.CONFIRMED
                for hypothesis in self.hypotheses
            )
            and not self.root_cause_confirmed
        ):
            raise ValueError("confirmed hypothesis requires confirmed case state")
        ranks = [item.rank for item in self.hypotheses]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("RCA hypotheses must have contiguous deterministic ranks")
        evidence_ids = {item.evidence_id for item in self.evidence}
        references = {
            reference
            for groups in (
                *(item.evidence_references for item in self.symptoms),
                *(item.evidence_references for item in self.timeline),
                *(item.supporting_evidence for item in self.hypotheses),
                *(item.contradicting_evidence for item in self.hypotheses),
                *(item.evidence_references for item in self.findings),
                self.provisional_statement.supporting_evidence,
                self.provisional_statement.contradicting_evidence,
            )
            for reference in groups
        }
        if not references <= evidence_ids:
            raise ValueError("RCA case contains unresolved evidence references")
