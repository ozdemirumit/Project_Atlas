"""ATLAS-024 SS8/SS9: analysis methods and finding contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class DeterministicAnalysisKind(StrEnum):
    """SS8.1's seven deterministic analysis methods."""

    THRESHOLD_AND_RULE_EVALUATION = "threshold_and_rule_evaluation"
    STATE_AND_CONFIGURATION_COMPARISON = "state_and_configuration_comparison"
    TIME_WINDOW_CORRELATION = "time_window_correlation"
    GRAPH_TRAVERSAL_AND_DEPENDENCY_ANALYSIS = "graph_traversal_and_dependency_analysis"
    KNOWN_ERROR_OR_SIGNATURE_MAPPING = "known_error_or_signature_mapping"
    CAPACITY_AND_TREND_CALCULATIONS = "capacity_and_trend_calculations"
    POLICY_INDEPENDENT_DATA_QUALITY_CHECKS = "policy_independent_data_quality_checks"


class AiAssistedAnalysisKind(StrEnum):
    """SS8.2's six AI-assisted analysis methods."""

    NATURAL_LANGUAGE_INTERPRETATION = "natural_language_interpretation"
    CROSS_SOURCE_SUMMARIZATION = "cross_source_summarization"
    HYPOTHESIS_GENERATION_AND_RANKING_PROPOSALS = "hypothesis_generation_and_ranking_proposals"
    SIMILAR_INCIDENT_COMPARISON = "similar_incident_comparison"
    EXPLANATION_AND_ALTERNATIVE_DRAFTING = "explanation_and_alternative_drafting"
    RUNBOOK_AND_VENDOR_GUIDANCE_INTERPRETATION = "runbook_and_vendor_guidance_interpretation"


def ai_output_requires_deterministic_validation() -> bool:
    """SS8.2: "AI output is a candidate input and requires schema, evidence, and deterministic
    validation." Always `True`."""
    return True


class FindingMethod(StrEnum):
    """SS9: "method: observed, deterministic rule, calculation, or AI-assisted inference.\""""

    OBSERVED = "observed"
    DETERMINISTIC_RULE = "deterministic_rule"
    CALCULATION = "calculation"
    AI_ASSISTED_INFERENCE = "ai_assisted_inference"


_EVIDENCE_REQUIRED_METHODS = frozenset(
    {FindingMethod.OBSERVED, FindingMethod.DETERMINISTIC_RULE, FindingMethod.CALCULATION}
)


def requires_supporting_evidence(method: FindingMethod) -> bool:
    """Mirrors Reasoning's analogous `requires_supporting_evidence` (`reasoning.claims`) for this
    module's own method taxonomy."""
    return method in _EVIDENCE_REQUIRED_METHODS


class DataQualityState(StrEnum):
    """SS9: "freshness and data-quality state.\""""

    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class FindingVersions:
    """SS9: "rule, model, agent, prompt, and schema versions as applicable.\""""

    rule_version: str | None
    model_version: str | None
    agent_version: str | None
    prompt_version: str | None
    schema_version: str | None


@dataclass(frozen=True, slots=True)
class DecisionFinding:
    """SS9's ten declared elements."""

    finding_id: str
    finding_type: str
    statement: str
    severity: str | None
    method: FindingMethod
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    target_id: str
    affected_scope: tuple[str, ...]
    first_observed_at: datetime
    last_observed_at: datetime
    data_quality_state: DataQualityState
    versions: FindingVersions
    confidence_basis: str
    unknowns: tuple[str, ...]
    recommended_validation: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.finding_id, "finding_id")
        if not self.finding_type.strip():
            raise ValueError("a decision finding requires a finding type")
        if not self.statement.strip():
            raise ValueError("a decision finding requires a statement")
        validate_stable_identifier(self.target_id, "target_id")
        if self.first_observed_at.tzinfo is None or self.last_observed_at.tzinfo is None:
            raise ValueError("first_observed_at and last_observed_at must be timezone-aware")
        if self.last_observed_at < self.first_observed_at:
            raise ValueError("last_observed_at must not precede first_observed_at")
        if not self.confidence_basis.strip():
            raise ValueError("a decision finding requires a confidence basis")

    @property
    def is_evidence_gap(self) -> bool:
        """Mirrors Reasoning's `ReasoningClaim.is_evidence_gap` construct-then-evaluate pattern:
        a finding whose method requires evidence but has none is still constructible, exposed as
        a checkable gap rather than blocked at construction."""
        return requires_supporting_evidence(self.method) and not self.supporting_evidence_ids
