"""ATLAS-041 SS16/SS17: causal reasoning rules and counterfactual analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reasoning.domain.models import EpistemicType


@dataclass(frozen=True, slots=True)
class CausalAssertion:
    """SS16: "correlation is not labeled root cause" -- a `CORRELATION`-typed assertion cannot
    also set `asserts_root_cause`, structurally. "Confirmed cause requires domain-defined
    evidence and validation criteria" -- `confirmation_criteria` can be present if and only if
    `is_confirmed_cause` is `True`."""

    claim_id: str
    epistemic_type: EpistemicType
    asserts_root_cause: bool
    contributing_causes: tuple[str, ...]
    latent_conditions: tuple[str, ...]
    is_confirmed_cause: bool
    confirmation_criteria: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.claim_id, "claim_id")
        if self.epistemic_type is EpistemicType.CORRELATION and self.asserts_root_cause:
            raise ValueError("SS16: correlation is not labeled root cause")
        if self.is_confirmed_cause and self.confirmation_criteria is None:
            raise ValueError(
                "SS16: confirmed cause requires domain-defined evidence and validation"
                " criteria -- confirmation_criteria is required"
            )
        if not self.is_confirmed_cause and self.confirmation_criteria is not None:
            raise ValueError(
                "confirmation_criteria is only meaningful when is_confirmed_cause is True"
            )


def temporal_precedence_alone_proves_causation() -> bool:
    """SS16: "temporal precedence is necessary for many causal claims but is not sufficient."
    Always `False`."""
    return False


def recent_change_alone_proves_causation() -> bool:
    """SS16: "a recent change is a candidate, not proof." Always `False`."""
    return False


def recovery_strengthens_hypothesis(
    *, alternative_causes_considered: bool, coincident_recovery_considered: bool
) -> bool:
    """SS16: "recovery after an action strengthens a hypothesis only when alternative causes and
    coincident recovery are considered.\""""
    return alternative_causes_considered and coincident_recovery_considered


def shared_upstream_dependency_explains_correlation(
    *, correlated_symptom_count: int, shared_dependency_id: str | None
) -> bool:
    """SS16: "a shared upstream dependency can explain correlated downstream symptoms.\""""
    return shared_dependency_id is not None and correlated_symptom_count >= 2


@dataclass(frozen=True, slots=True)
class HumanConfirmation:
    """SS16: "human confirmation is preserved as evidence with identity and time, not as
    infallible truth." No field on this type can mark a confirmation as beyond question -- it is
    always just evidence, structurally, by the absence of any such field."""

    confirmed_by: str
    confirmed_at: datetime
    statement: str

    def __post_init__(self) -> None:
        if not self.confirmed_by.strip():
            raise ValueError("a human confirmation requires who confirmed it")
        if self.confirmed_at.tzinfo is None:
            raise ValueError("confirmed_at must be timezone-aware")
        if not self.statement.strip():
            raise ValueError("a human confirmation requires a statement")


class CounterfactualQuestionKind(StrEnum):
    """SS17's six questions Atlas asks for material decisions."""

    EXPECTED_IF_LEADING_HYPOTHESIS_FALSE = "expected_if_leading_hypothesis_false"
    EVIDENCE_EQUALLY_EXPLAINED_BY_ANOTHER_CAUSE = "evidence_equally_explained_by_another_cause"
    WHAT_CHANGED_WHILE_PEERS_STABLE = "what_changed_while_peers_stable"
    REDUNDANT_PATH_THAT_SHOULD_HAVE_PREVENTED_IMPACT = (
        "redundant_path_that_should_have_prevented_impact"
    )
    OBSERVATION_SOURCE_FAULTY_OR_STALE = "observation_source_faulty_or_stale"
    CHECK_WOULD_PRODUCE_INDISTINGUISHABLE_RESULT = "check_would_produce_indistinguishable_result"


class CounterfactualBasis(StrEnum):
    """SS17: "counterfactual statements are labeled as estimates unless supported by a validated
    simulator or historical experiment.\""""

    ESTIMATE = "estimate"
    VALIDATED_SIMULATOR = "validated_simulator"
    HISTORICAL_EXPERIMENT = "historical_experiment"


@dataclass(frozen=True, slots=True)
class CounterfactualStatement:
    statement_id: str
    question_kind: CounterfactualQuestionKind
    answer: str
    basis: CounterfactualBasis
    supporting_reference: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.statement_id, "statement_id")
        if not self.answer.strip():
            raise ValueError("a counterfactual statement requires an answer")
        is_estimate = self.basis is CounterfactualBasis.ESTIMATE
        if not is_estimate and self.supporting_reference is None:
            raise ValueError(
                "a counterfactual statement backed by a simulator or historical experiment"
                " requires a supporting_reference"
            )
        if is_estimate and self.supporting_reference is not None:
            raise ValueError("supporting_reference is only meaningful when basis is not ESTIMATE")
