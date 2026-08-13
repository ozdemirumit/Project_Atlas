from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel


def _ids(*values: str) -> bool:
    return all(value.strip() and len(value) <= 256 for value in values)


def _digests(*values: str) -> bool:
    return all(
        len(value) == 64 and all(char in "0123456789abcdef" for char in value) for value in values
    )


RISK_LEVELS = {"low", "moderate", "high", "critical", "unknown"}


@dataclass(frozen=True, slots=True)
class ProtectedCandidateRiskRecoveryPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_impact_schema: str
    required_impact_state: str
    required_evidence_schema: str
    required_evidence_snapshot_id: str
    required_report_schema: str
    required_receipt_schema: str
    required_assessor_id: str
    required_assessor_attestor_id: str
    required_risk_dimensions: tuple[str, ...]
    maximum_candidate_count: int
    maximum_evidence_item_count: int
    maximum_gap_count: int
    maximum_unknown_count: int
    maximum_duration_minutes: int
    maximum_output_bytes: int
    retention_minutes: int
    required_assurance_level: AssuranceLevel
    classification_ceiling: str
    browser_binding_key_digest: str
    risk_floor_profile_digest: str
    safety_profile_digest: str
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _ids(
                self.policy_id,
                self.schema_version,
                self.organization_id,
                self.environment_id,
                self.policy_version,
                self.required_impact_schema,
                self.required_impact_state,
                self.required_evidence_schema,
                self.required_evidence_snapshot_id,
                self.required_report_schema,
                self.required_receipt_schema,
                self.required_assessor_id,
                self.required_assessor_attestor_id,
                self.classification_ceiling,
                self.signed_by,
            )
            or len(self.required_risk_dimensions) != 7
            or len(set(self.required_risk_dimensions)) != 7
            or not 3 <= self.maximum_candidate_count <= 5
            or min(
                self.maximum_evidence_item_count,
                self.maximum_gap_count,
                self.maximum_unknown_count,
                self.maximum_duration_minutes,
                self.maximum_output_bytes,
                self.retention_minutes,
            )
            < 1
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not self.signature_verified
            or not _digests(
                self.browser_binding_key_digest,
                self.risk_floor_profile_digest,
                self.safety_profile_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Protected candidate risk-recovery policy is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedOperationalEvidenceItem:
    evidence_id: str
    evidence_kind: str
    assertion_kind: str
    subject_scope: str
    value: str
    evidence_references: tuple[str, ...]
    sample_count: int
    observed_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            not _ids(
                self.evidence_id,
                self.evidence_kind,
                self.assertion_kind,
                self.subject_scope,
                self.value,
            )
            or self.assertion_kind not in {"observed", "declared", "simulated", "historical"}
            or not self.evidence_references
            or self.sample_count < 1
            or self.observed_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.observed_at < self.expires_at
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Protected operational evidence item is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedOperationalEvidenceSnapshot:
    snapshot_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    source_id: str
    classification: str
    freshness: str
    completeness: str
    items: tuple[ProtectedOperationalEvidenceItem, ...]
    gaps: tuple[str, ...]
    unknowns: tuple[str, ...]
    coverage_digest: str
    generated_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _ids(
                self.snapshot_id,
                self.schema_version,
                self.organization_id,
                self.environment_id,
                self.source_id,
                self.classification,
                self.freshness,
                self.completeness,
            )
            or not self.items
            or len({item.evidence_id for item in self.items}) != len(self.items)
            or not self.gaps
            or not self.unknowns
            or self.generated_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.generated_at < self.expires_at
            or not _digests(self.coverage_digest, self.canonical_digest)
        ):
            raise ValueError("Protected operational evidence snapshot is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateRiskRecoveryInstruction:
    completion_id: str
    impact_analysis_id: str
    impact_digest: str
    candidate_set_id: str
    candidate_set_digest: str
    completion_authorization_digest: str
    policy_id: str
    policy_digest: str
    evidence_snapshot_id: str
    evidence_snapshot_digest: str
    required_risk_dimensions: tuple[str, ...]
    maximum_candidate_count: int
    maximum_evidence_item_count: int
    maximum_gap_count: int
    maximum_unknown_count: int
    maximum_duration_minutes: int
    maximum_output_bytes: int
    required_report_schema: str
    risk_floor_profile_digest: str
    safety_profile_digest: str
    requested_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProtectedCandidateRiskDimension:
    dimension: str
    level: str
    rationale: str
    evidence_references: tuple[str, ...]
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            not _ids(self.dimension)
            or self.level not in RISK_LEVELS
            or not self.rationale.strip()
            or not self.evidence_references
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Protected candidate risk dimension is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateDurationEstimate:
    minimum_minutes: int
    maximum_minutes: int
    basis: str
    confidence: str
    evidence_references: tuple[str, ...]
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.minimum_minutes < 0
            or self.maximum_minutes < self.minimum_minutes
            or not self.basis.strip()
            or self.confidence not in {"low", "moderate", "high", "unknown"}
            or not self.evidence_references
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Protected candidate duration estimate is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateInterruptionEstimate:
    expected_mode: str
    worst_credible_mode: str
    expected_minimum_minutes: int
    expected_maximum_minutes: int
    worst_minimum_minutes: int
    worst_maximum_minutes: int
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    evidence_references: tuple[str, ...]
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            not _ids(self.expected_mode, self.worst_credible_mode)
            or min(
                self.expected_minimum_minutes,
                self.expected_maximum_minutes,
                self.worst_minimum_minutes,
                self.worst_maximum_minutes,
            )
            < 0
            or self.expected_maximum_minutes < self.expected_minimum_minutes
            or self.worst_maximum_minutes < self.worst_minimum_minutes
            or self.worst_maximum_minutes < self.expected_maximum_minutes
            or not self.assumptions
            or not self.unknowns
            or not self.evidence_references
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Protected candidate interruption estimate is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateRecoveryAssessment:
    strategy: str
    feasibility: str
    point_of_no_return: str
    trigger_conditions: tuple[str, ...]
    duration: ProtectedCandidateDurationEstimate
    data_implications: str
    verification_criteria: tuple[str, ...]
    gaps: tuple[str, ...]
    evidence_references: tuple[str, ...]
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            not _ids(self.strategy, self.point_of_no_return)
            or self.feasibility not in {"feasible", "not_required", "unknown", "blocked"}
            or not self.trigger_conditions
            or not self.data_implications.strip()
            or not self.verification_criteria
            or not self.gaps
            or not self.evidence_references
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Protected candidate recovery assessment is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateRiskRecoveryEntry:
    candidate_id: str
    candidate_digest: str
    impact_entry_digest: str
    risk_dimensions: tuple[ProtectedCandidateRiskDimension, ...]
    overall_risk: str
    work_duration: ProtectedCandidateDurationEstimate
    interruption: ProtectedCandidateInterruptionEstimate
    recovery: ProtectedCandidateRecoveryAssessment
    assumption_count: int
    conflict_count: int
    gap_count: int
    unknown_count: int
    impact_complete: bool = True
    interruption_established: bool = True
    duration_established: bool = True
    risk_completed: bool = True
    recovery_completed: bool = True
    preferred: bool = False
    ready_for_review: bool = False
    execution_authorized: bool = False
    canonical_digest: str = ""

    def __post_init__(self) -> None:
        if (
            not _ids(self.candidate_id)
            or not _digests(
                self.candidate_digest,
                self.impact_entry_digest,
                self.canonical_digest,
            )
            or len(self.risk_dimensions) != 7
            or len({item.dimension for item in self.risk_dimensions}) != 7
            or self.overall_risk not in RISK_LEVELS
            or min(
                self.assumption_count,
                self.conflict_count,
                self.gap_count,
                self.unknown_count,
            )
            < 0
            or not all(
                (
                    self.impact_complete,
                    self.interruption_established,
                    self.duration_established,
                    self.risk_completed,
                    self.recovery_completed,
                )
            )
            or any((self.preferred, self.ready_for_review, self.execution_authorized))
        ):
            raise ValueError("Protected candidate risk-recovery entry is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateRiskRecoveryReport:
    completion_id: str
    schema_version: str
    version: int
    impact_analysis_id: str
    impact_digest: str
    candidate_set_id: str
    candidate_set_digest: str
    policy_digest: str
    evidence_snapshot_id: str
    evidence_snapshot_digest: str
    entries: tuple[ProtectedCandidateRiskRecoveryEntry, ...]
    coverage_digest: str
    risk_digest: str
    duration_digest: str
    interruption_digest: str
    recovery_digest: str
    unknown_digest: str
    safety_digest: str
    byte_count: int
    completed_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _ids(
                self.completion_id,
                self.schema_version,
                self.impact_analysis_id,
                self.candidate_set_id,
                self.evidence_snapshot_id,
            )
            or not 3 <= len(self.entries) <= 5
            or len({entry.candidate_id for entry in self.entries}) != len(self.entries)
            or self.byte_count < 1
            or self.completed_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.completed_at < self.expires_at
            or not _digests(
                self.impact_digest,
                self.candidate_set_digest,
                self.policy_digest,
                self.evidence_snapshot_digest,
                self.coverage_digest,
                self.risk_digest,
                self.duration_digest,
                self.interruption_digest,
                self.recovery_digest,
                self.unknown_digest,
                self.safety_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Protected candidate risk-recovery report is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateRiskRecoveryReceipt:
    completion_id: str
    schema_version: str
    version: int
    assessor_id: str
    attested_by: str
    impact_analysis_id: str
    impact_digest: str
    candidate_set_id: str
    candidate_set_digest: str
    completion_authorization_digest: str
    policy_digest: str
    evidence_snapshot_id: str
    evidence_snapshot_digest: str
    report_digest: str
    coverage_digest: str
    risk_digest: str
    duration_digest: str
    interruption_digest: str
    recovery_digest: str
    unknown_digest: str
    safety_digest: str
    cleanup_digest: str
    candidate_count: int
    evidence_item_count: int
    low_risk_count: int
    moderate_risk_count: int
    high_risk_count: int
    critical_risk_count: int
    unknown_risk_count: int
    maximum_risk: str
    interruption_possible_count: int
    recovery_feasible_count: int
    recovery_unknown_count: int
    recovery_blocked_count: int
    work_minimum_minutes: int
    work_maximum_minutes: int
    interruption_minimum_minutes: int
    interruption_maximum_minutes: int
    recovery_minimum_minutes: int
    recovery_maximum_minutes: int
    gap_count: int
    unknown_count: int
    byte_count: int
    completed_at: datetime
    expires_at: datetime
    source_verified: bool
    evidence_verified: bool
    complete_candidate_coverage_verified: bool
    conservative_risk_floor_verified: bool
    ranges_bounded_verified: bool
    recovery_coverage_verified: bool
    no_preference_assigned: bool
    no_model_used: bool
    cleanup_verified: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        risk_total = (
            self.low_risk_count
            + self.moderate_risk_count
            + self.high_risk_count
            + self.critical_risk_count
            + self.unknown_risk_count
        )
        if (
            self.version != 1
            or not _ids(
                self.completion_id,
                self.schema_version,
                self.assessor_id,
                self.attested_by,
                self.impact_analysis_id,
                self.candidate_set_id,
                self.evidence_snapshot_id,
            )
            or self.maximum_risk not in RISK_LEVELS
            or risk_total != self.candidate_count
            or not 3 <= self.candidate_count <= 5
            or self.evidence_item_count < 1
            or min(
                self.interruption_possible_count,
                self.recovery_feasible_count,
                self.recovery_unknown_count,
                self.recovery_blocked_count,
                self.work_minimum_minutes,
                self.work_maximum_minutes,
                self.interruption_minimum_minutes,
                self.interruption_maximum_minutes,
                self.recovery_minimum_minutes,
                self.recovery_maximum_minutes,
                self.gap_count,
                self.unknown_count,
                self.byte_count,
            )
            < 0
            or self.byte_count < 1
            or self.completed_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.completed_at < self.expires_at
            or not all(
                (
                    self.source_verified,
                    self.evidence_verified,
                    self.complete_candidate_coverage_verified,
                    self.conservative_risk_floor_verified,
                    self.ranges_bounded_verified,
                    self.recovery_coverage_verified,
                    self.no_preference_assigned,
                    self.no_model_used,
                    self.cleanup_verified,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.impact_digest,
                self.candidate_set_digest,
                self.completion_authorization_digest,
                self.policy_digest,
                self.evidence_snapshot_digest,
                self.report_digest,
                self.coverage_digest,
                self.risk_digest,
                self.duration_digest,
                self.interruption_digest,
                self.recovery_digest,
                self.unknown_digest,
                self.safety_digest,
                self.cleanup_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Protected candidate risk-recovery receipt is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateRiskRecoveryClaim:
    claim_id: str
    schema_version: str
    version: int
    completion_id: str
    impact_analysis_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _ids(
                self.claim_id,
                self.schema_version,
                self.completion_id,
                self.impact_analysis_id,
                self.organization_id,
                self.environment_id,
            )
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Protected candidate risk-recovery claim is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateRiskRecoveryRecord:
    completion_id: str
    schema_version: str
    version: int
    claim_id: str
    impact_analysis_id: str
    impact_digest: str
    candidate_set_id: str
    candidate_set_digest: str
    presentation_id: str
    answer_digest: str
    adjudication_id: str
    invocation_id: str
    context_id: str
    organization_id: str
    environment_id: str
    classification: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    completion_policy_id: str
    completion_policy_digest: str
    completion_policy_version: str
    assessor_id: str
    completion_receipt_digest: str
    completion_authorization_digest: str
    protected_report_digest: str
    evidence_snapshot_id: str
    evidence_snapshot_digest: str
    evidence_snapshot_generated_at: datetime
    evidence_freshness: str
    evidence_completeness: str
    evidence_coverage_digest: str
    coverage_digest: str
    risk_digest: str
    duration_digest: str
    interruption_digest: str
    recovery_digest: str
    unknown_digest: str
    safety_digest: str
    cleanup_digest: str
    candidate_count: int
    evidence_item_count: int
    low_risk_count: int
    moderate_risk_count: int
    high_risk_count: int
    critical_risk_count: int
    unknown_risk_count: int
    maximum_risk: str
    interruption_possible_count: int
    recovery_feasible_count: int
    recovery_unknown_count: int
    recovery_blocked_count: int
    work_minimum_minutes: int
    work_maximum_minutes: int
    interruption_minimum_minutes: int
    interruption_maximum_minutes: int
    recovery_minimum_minutes: int
    recovery_maximum_minutes: int
    gap_count: int
    unknown_count: int
    byte_count: int
    completed_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    safety_notice: str
    canonical_digest: str
    service_impact_analyzed: bool = True
    impact_complete: bool = True
    outage_confirmed: bool = False
    interruption_established: bool = True
    duration_established: bool = True
    risk_completed: bool = True
    recovery_completed: bool = True
    recommendation_complete: bool = False
    recommendation_presented: bool = False
    recommendation_ready_for_review: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        risk_total = (
            self.low_risk_count
            + self.moderate_risk_count
            + self.high_risk_count
            + self.critical_risk_count
            + self.unknown_risk_count
        )
        if (
            self.version != 1
            or self.instance_state != "protected_candidate_risk_recovery_completed"
            or not all(
                (
                    self.service_impact_analyzed,
                    self.impact_complete,
                    self.interruption_established,
                    self.duration_established,
                    self.risk_completed,
                    self.recovery_completed,
                )
            )
            or any(
                (
                    self.outage_confirmed,
                    self.recommendation_complete,
                    self.recommendation_presented,
                    self.recommendation_ready_for_review,
                    self.recommendation_approved,
                    self.workflow_created,
                    self.execution_authorized,
                    self.deployment_authorized,
                    self.infrastructure_mutated,
                )
            )
            or risk_total != self.candidate_count
            or not 3 <= self.candidate_count <= 5
            or self.maximum_risk not in RISK_LEVELS
            or min(
                self.evidence_item_count,
                self.interruption_possible_count,
                self.recovery_feasible_count,
                self.recovery_unknown_count,
                self.recovery_blocked_count,
                self.work_minimum_minutes,
                self.work_maximum_minutes,
                self.interruption_minimum_minutes,
                self.interruption_maximum_minutes,
                self.recovery_minimum_minutes,
                self.recovery_maximum_minutes,
                self.gap_count,
                self.unknown_count,
                self.byte_count,
            )
            < 0
            or self.evidence_item_count < 1
            or self.byte_count < 1
            or not 20 <= len(self.purpose.strip()) <= 1_000
            or not self.safety_notice.strip()
            or self.evidence_snapshot_generated_at.tzinfo is None
            or self.completed_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.completed_at < self.expires_at
        ):
            raise ValueError("Protected candidate risk-recovery record is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedCandidateRiskRecoveryManifest:
    completion_id: str
    impact_analysis_id: str
    candidate_set_id: str
    presentation_id: str
    evidence_snapshot_id: str
    evidence_snapshot_digest: str
    evidence_snapshot_generated_at: datetime
    evidence_freshness: str
    evidence_completeness: str
    evidence_coverage_digest: str
    candidate_count: int
    evidence_item_count: int
    low_risk_count: int
    moderate_risk_count: int
    high_risk_count: int
    critical_risk_count: int
    unknown_risk_count: int
    maximum_risk: str
    interruption_possible_count: int
    recovery_feasible_count: int
    recovery_unknown_count: int
    recovery_blocked_count: int
    work_minimum_minutes: int
    work_maximum_minutes: int
    interruption_minimum_minutes: int
    interruption_maximum_minutes: int
    recovery_minimum_minutes: int
    recovery_maximum_minutes: int
    gap_count: int
    unknown_count: int
    coverage_digest: str
    risk_digest: str
    duration_digest: str
    interruption_digest: str
    recovery_digest: str
    unknown_digest: str
    safety_digest: str
    completed_at: datetime
    expires_at: datetime
    safety_notice: str


@dataclass(frozen=True, slots=True)
class ProtectedCandidateRiskRecoveryResult:
    record: ProtectedCandidateRiskRecoveryRecord
    manifest: ProtectedCandidateRiskRecoveryManifest
