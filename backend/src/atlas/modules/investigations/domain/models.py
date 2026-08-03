from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification


class EpistemicType(StrEnum):
    OBSERVATION = "observation"
    RETRIEVED_FACT = "retrieved_fact"
    CALCULATED_FINDING = "calculated_finding"
    CORRELATION = "correlation"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    ASSUMPTION = "assumption"
    UNKNOWN = "unknown"
    RECOMMENDATION = "recommendation"


class ConfidenceCategory(StrEnum):
    INSUFFICIENT = "insufficient"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class HypothesisState(StrEnum):
    PROPOSED = "proposed"
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class FreshnessState(StrEnum):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class InvestigationRequest:
    target_id: str
    question: str
    intended_decision: str
    window_start: datetime
    window_end: datetime
    max_evidence_records: int

    def __post_init__(self) -> None:
        if self.window_start.tzinfo is None or self.window_end.tzinfo is None:
            raise ValueError("investigation time window must be timezone-aware")
        if self.window_end <= self.window_start:
            raise ValueError("investigation time window must be increasing")
        if not self.question.strip() or len(self.question) > 500:
            raise ValueError("investigation question must contain 1 to 500 characters")
        if not self.intended_decision.strip() or len(self.intended_decision) > 240:
            raise ValueError("intended decision must contain 1 to 240 characters")
        if not 1 <= self.max_evidence_records <= 20:
            raise ValueError("evidence budget must be between 1 and 20")


@dataclass(frozen=True, slots=True)
class EvidenceUnit:
    evidence_id: str
    artifact_version: str
    source_type: str
    source_system: str
    source_version: str
    target_id: str
    observed_at: datetime
    applicable_from: datetime
    applicable_to: datetime | None
    freshness: FreshnessState
    classification: DataClassification
    authorization_reference: str
    collection_method: str
    summary: str
    integrity: str
    completeness: str
    quality_limitations: tuple[str, ...]
    citation: str

    def __post_init__(self) -> None:
        timestamps = (self.observed_at, self.applicable_from)
        if any(value.tzinfo is None for value in timestamps):
            raise ValueError("evidence timestamps must be timezone-aware")
        if self.applicable_to is not None and self.applicable_to.tzinfo is None:
            raise ValueError("applicable_to must be timezone-aware")
        if not all(
            value.strip()
            for value in (
                self.evidence_id,
                self.source_system,
                self.target_id,
                self.authorization_reference,
                self.summary,
                self.citation,
            )
        ):
            raise ValueError("evidence identity, scope, summary, and citation are required")


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    event_id: str
    event_type: str
    summary: str
    occurred_at: datetime
    observed_at: datetime
    ingested_at: datetime
    evidence_references: tuple[str, ...]
    clock_quality: str

    def __post_init__(self) -> None:
        if any(
            value.tzinfo is None for value in (self.occurred_at, self.observed_at, self.ingested_at)
        ):
            raise ValueError("timeline timestamps must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("timeline events require evidence")


@dataclass(frozen=True, slots=True)
class Claim:
    claim_id: str
    epistemic_type: EpistemicType
    text: str
    scope: str
    window_start: datetime
    window_end: datetime
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]
    assumptions: tuple[str, ...]
    confidence: ConfidenceCategory
    supporting_factors: tuple[str, ...]
    limiting_factors: tuple[str, ...]
    validation_state: str

    def __post_init__(self) -> None:
        if self.window_start.tzinfo is None or self.window_end.tzinfo is None:
            raise ValueError("claim time window must be timezone-aware")
        if not self.text.strip() or not self.scope.strip():
            raise ValueError("claims require text and scope")


@dataclass(frozen=True, slots=True)
class DiscriminatingCheck:
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

    def __post_init__(self) -> None:
        if self.capability_class != "C1":
            raise ValueError("investigation checks are limited to C1 read-only capabilities")
        if self.timeout_seconds < 1:
            raise ValueError("check timeout must be positive")


@dataclass(frozen=True, slots=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    state: HypothesisState
    expected_consequences: tuple[str, ...]
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]
    assumptions: tuple[str, ...]
    confidence: ConfidenceCategory
    confidence_rationale: str
    limiting_factors: tuple[str, ...]
    discriminating_checks: tuple[DiscriminatingCheck, ...]

    def __post_init__(self) -> None:
        if not self.statement.strip() or not self.confidence_rationale.strip():
            raise ValueError("hypotheses require a statement and confidence rationale")
        if not self.discriminating_checks:
            raise ValueError("hypotheses require at least one discriminating check")


@dataclass(frozen=True, slots=True)
class ReasoningSummary:
    known: tuple[str, ...]
    inferred: tuple[str, ...]
    alternatives: tuple[str, ...]
    unknowns: tuple[str, ...]
    confidence: ConfidenceCategory
    confidence_rationale: str
    safest_next_check: str
    supported_decision: str
    unsupported_decision: str


@dataclass(frozen=True, slots=True)
class ReasoningArtifact:
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
    evidence: tuple[EvidenceUnit, ...]
    timeline: tuple[TimelineEvent, ...]
    claims: tuple[Claim, ...]
    hypotheses: tuple[Hypothesis, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    conflicts: tuple[str, ...]
    excluded_evidence: tuple[str, ...]
    stop_reason: str
    recommended_next_evidence: tuple[str, ...]
    component_versions: tuple[str, ...]
    summary: ReasoningSummary
    data_profile: str
    root_cause_confirmed: bool
    outage_confirmed: bool
    safety_notice: str

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("artifact version must be positive")
        if self.created_at.tzinfo is None:
            raise ValueError("artifact created_at must be timezone-aware")
        if self.root_cause_confirmed or self.outage_confirmed:
            raise ValueError("this investigation slice cannot confirm root cause or outage")
        evidence_ids = {item.evidence_id for item in self.evidence}
        if len(evidence_ids) != len(self.evidence):
            raise ValueError("evidence identifiers must be unique")
        references = {
            reference
            for groups in (
                *(item.evidence_references for item in self.timeline),
                *(item.supporting_evidence for item in self.claims),
                *(item.contradicting_evidence for item in self.claims),
                *(item.supporting_evidence for item in self.hypotheses),
                *(item.contradicting_evidence for item in self.hypotheses),
            )
            for reference in groups
        }
        if not references <= evidence_ids:
            raise ValueError("reasoning artifact contains unresolved evidence references")
        material_types = {
            EpistemicType.OBSERVATION,
            EpistemicType.RETRIEVED_FACT,
            EpistemicType.CALCULATED_FINDING,
            EpistemicType.CORRELATION,
            EpistemicType.INFERENCE,
            EpistemicType.HYPOTHESIS,
        }
        if any(
            claim.epistemic_type in material_types and not claim.supporting_evidence
            for claim in self.claims
        ):
            raise ValueError("material claims require supporting evidence")
