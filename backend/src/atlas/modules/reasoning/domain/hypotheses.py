"""ATLAS-041 SS13/SS14: hypothesis ledger and generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reasoning.domain.claims import ConfidenceCategory

_INITIAL_STATE_NAME = "PROPOSED"


class HypothesisState(StrEnum):
    """SS13's six states."""

    PROPOSED = "proposed"
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    REJECTED = "rejected"
    CONFIRMED = "confirmed"
    UNRESOLVED = "unresolved"


class HypothesisSourceKind(StrEnum):
    """SS14's seven named candidate-cause sources."""

    CURRENT_SYMPTOMS_AND_TOPOLOGY = "current_symptoms_and_topology"
    DOMAIN_FAULT_MODEL = "domain_fault_model"
    RECENT_CHANGE_OR_CONFIGURATION_DRIFT = "recent_change_or_configuration_drift"
    KNOWN_PRODUCT_VERSION_DEFECT = "known_product_version_defect"
    HISTORICAL_INCIDENT = "historical_incident"
    RESOURCE_DEPENDENCY_OR_CONTROL_PLANE_FAILURE = "resource_dependency_or_control_plane_failure"
    USER_SUPPLIED = "user_supplied"


@dataclass(frozen=True, slots=True)
class DiscriminatingCheckReference:
    """SS13: "safe checks that would discriminate it from alternatives" -- referenced by ID; the
    full discriminating-check contract is SS15's own slice."""

    check_reference: str
    expected_result_if_true: str

    def __post_init__(self) -> None:
        if not self.check_reference.strip():
            raise ValueError("a discriminating check reference requires a check_reference")
        if not self.expected_result_if_true.strip():
            raise ValueError("a discriminating check reference requires expected_result_if_true")


@dataclass(frozen=True, slots=True)
class ReasoningHypothesis:
    """SS13's nine declared elements."""

    hypothesis_id: str
    causal_statement: str
    source_kind: HypothesisSourceKind
    initiating_factors: tuple[str, ...]
    contributing_factors: tuple[str, ...]
    amplifying_factors: tuple[str, ...]
    scope_target_ids: tuple[str, ...]
    onset: str
    expected_observable_consequences: tuple[str, ...]
    supporting_evidence_ids: tuple[str, ...]
    contradicting_or_absent_evidence_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    known_confounders: tuple[str, ...]
    discriminating_checks: tuple[DiscriminatingCheckReference, ...]
    state: HypothesisState
    confidence: ConfidenceCategory
    reason_for_state_change: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.hypothesis_id, "hypothesis_id")
        if not self.causal_statement.strip():
            raise ValueError("a hypothesis requires a concise causal statement")
        if not self.scope_target_ids:
            raise ValueError("a hypothesis requires at least one scope target")
        if not self.onset.strip():
            raise ValueError("a hypothesis requires an onset")
        is_initial = self.state is HypothesisState.PROPOSED
        if not is_initial and self.reason_for_state_change is None:
            raise ValueError(
                f"a hypothesis in state {self.state.value} requires a reason for the state"
                f" change (every state beyond {_INITIAL_STATE_NAME} is itself a change)"
            )
        if is_initial and self.reason_for_state_change is not None:
            raise ValueError(
                "reason_for_state_change is only meaningful once the hypothesis has moved"
                f" beyond {_INITIAL_STATE_NAME}"
            )
        if self.state is HypothesisState.CONFIRMED and not self.supporting_evidence_ids:
            raise ValueError("a confirmed hypothesis requires supporting evidence")


def active_hypotheses(
    hypotheses: tuple[ReasoningHypothesis, ...],
) -> tuple[ReasoningHypothesis, ...]:
    """SS13: "Atlas keeps multiple plausible hypotheses until evidence discriminates among
    them." Every hypothesis not yet `REJECTED` remains active -- rejection is what "evidence
    discriminates" looks like for a hypothesis that lost; a `CONFIRMED` hypothesis is the
    resolved answer and stays in the set rather than being discarded."""
    return tuple(
        hypothesis for hypothesis in hypotheses if hypothesis.state is not HypothesisState.REJECTED
    )


@dataclass(frozen=True, slots=True)
class HypothesisGenerationBudget:
    """SS14: "generation is bounded and diverse enough to avoid fixation.\""""

    maximum_hypotheses: int
    minimum_distinct_source_kinds: int

    def __post_init__(self) -> None:
        if self.maximum_hypotheses < 1:
            raise ValueError("maximum_hypotheses must be positive")
        if self.minimum_distinct_source_kinds < 1:
            raise ValueError("minimum_distinct_source_kinds must be positive")


def satisfies_diversity_requirement(
    hypotheses: tuple[ReasoningHypothesis, ...], *, budget: HypothesisGenerationBudget
) -> bool:
    """SS14: "generation is bounded and diverse enough to avoid fixation." Diversity is only
    required up to how many hypotheses actually exist -- a single generated hypothesis cannot be
    "diverse" across multiple sources by itself."""
    if len(hypotheses) > budget.maximum_hypotheses:
        return False
    distinct_sources = {hypothesis.source_kind for hypothesis in hypotheses}
    required = min(budget.minimum_distinct_source_kinds, len(hypotheses))
    return len(distinct_sources) >= required
