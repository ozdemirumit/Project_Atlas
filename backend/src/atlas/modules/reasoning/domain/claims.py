"""ATLAS-041 SS6: claim contract.

`requires_supporting_evidence`/`ReasoningClaim.is_evidence_gap` mirror the "construct-then-
evaluate" pattern already established in this codebase (e.g. `explainability.models.
ExplanationClaim.is_evidence_gap`): a claim of an evidence-required epistemic type with no
supporting evidence must still be constructible -- missing evidence is a checkable gap, not a
construction-time error -- matching SS5's "missing evidence is represented as a gap, not an
empty citation" applied here to claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reasoning.domain.models import EpistemicType


class ConfidenceCategory(StrEnum):
    """SS18's five calibrated confidence categories."""

    INSUFFICIENT = "insufficient"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CONFIRMED = "confirmed"


class ClaimValidationState(StrEnum):
    """SS6: "validation state and reviewer feedback.\""""

    UNVALIDATED = "unvalidated"
    VALIDATED = "validated"
    DISPUTED = "disputed"
    REJECTED = "rejected"


class ClaimLifecycleState(StrEnum):
    """SS6: "claims can be superseded, corrected, or withdrawn without rewriting historical
    reasoning.\""""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CORRECTED = "corrected"
    WITHDRAWN = "withdrawn"


class ReasoningRelationshipKind(StrEnum):
    """SS6: "relationships to hypotheses, findings, decisions, and recommendations.\""""

    HYPOTHESIS = "hypothesis"
    FINDING = "finding"
    DECISION = "decision"
    RECOMMENDATION = "recommendation"


@dataclass(frozen=True, slots=True)
class ReasoningRelationship:
    kind: ReasoningRelationshipKind
    reference_id: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.reference_id, "reference_id")


_EVIDENCE_REQUIRED_EPISTEMIC_TYPES = frozenset(
    {
        EpistemicType.OBSERVATION,
        EpistemicType.RETRIEVED_FACT,
        EpistemicType.CALCULATED_FINDING,
        EpistemicType.CORRELATION,
    }
)


def requires_supporting_evidence(epistemic_type: EpistemicType) -> bool:
    """Mirrors Guardrails' analogous evidence-required-claim-type check
    (`reasoning_guardrails._EVIDENCE_REQUIRED_CLAIM_TYPES`) for this module's own, richer
    epistemic taxonomy (slice 1)."""
    return epistemic_type in _EVIDENCE_REQUIRED_EPISTEMIC_TYPES


@dataclass(frozen=True, slots=True)
class ReasoningClaim:
    """SS6's ten declared elements."""

    claim_id: str
    epistemic_type: EpistemicType
    text: str
    scope_target_id: str
    time_window_start: datetime
    time_window_end: datetime | None
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    dependencies: tuple[str, ...]
    confidence: ConfidenceCategory
    confidence_rationale: str
    agent_version: str | None
    deterministic_method_version: str | None
    validation_state: ClaimValidationState
    reviewer_feedback: str | None
    relationships: tuple[ReasoningRelationship, ...]
    lifecycle_state: ClaimLifecycleState
    superseded_by_claim_id: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.claim_id, "claim_id")
        validate_stable_identifier(self.scope_target_id, "scope_target_id")
        if not self.text.strip():
            raise ValueError("a reasoning claim requires claim text")
        if self.time_window_start.tzinfo is None:
            raise ValueError("time_window_start must be timezone-aware")
        if self.time_window_end is not None:
            if self.time_window_end.tzinfo is None:
                raise ValueError("time_window_end must be timezone-aware")
            if self.time_window_end < self.time_window_start:
                raise ValueError("time_window_end must not precede time_window_start")
        if not self.confidence_rationale.strip():
            raise ValueError("a reasoning claim requires a confidence rationale")
        if (
            self.validation_state is ClaimValidationState.DISPUTED
            and self.reviewer_feedback is None
        ):
            raise ValueError("a disputed claim requires reviewer feedback")
        is_superseded = self.lifecycle_state is ClaimLifecycleState.SUPERSEDED
        if is_superseded and self.superseded_by_claim_id is None:
            raise ValueError("a superseded claim requires the claim that superseded it")
        if not is_superseded and self.superseded_by_claim_id is not None:
            raise ValueError("superseded_by_claim_id is only meaningful for a SUPERSEDED claim")

    @property
    def is_evidence_gap(self) -> bool:
        return (
            requires_supporting_evidence(self.epistemic_type) and not self.supporting_evidence_ids
        )

    @property
    def has_contradicting_evidence(self) -> bool:
        return bool(self.contradicting_evidence_ids)
