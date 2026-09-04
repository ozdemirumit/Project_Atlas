"""ATLAS-047 SS14: reasoning guardrails.

Models claims as a closed, typed taxonomy rather than free text, so "facts, calculations,
correlations, inferences, hypotheses, assumptions, and unknowns remain distinct" (SS14) by
construction -- a caller cannot produce a `ReasoningClaim` without picking one of the seven types.
Confidence is a coarse three-level scale, not a numeric probability, matching SS14's "confidence
... is not fabricated as precise probability."
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ClaimType(StrEnum):
    FACT = "fact"
    CALCULATION = "calculation"
    CORRELATION = "correlation"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    ASSUMPTION = "assumption"
    UNKNOWN = "unknown"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


_EVIDENCE_REQUIRED_CLAIM_TYPES = frozenset(
    {ClaimType.FACT, ClaimType.CALCULATION, ClaimType.CORRELATION}
)

_CAUSAL_LANGUAGE = re.compile(r"(?i)\b(causes?|caused by|leads? to|results? in|due to)\b")


@dataclass(frozen=True, slots=True)
class ReasoningClaim:
    """SS14: "current target, version, and time applicability are required" -- every claim
    carries what it applies to and when, not just what it says."""

    claim_id: str
    claim_type: ClaimType
    statement: str
    confidence: ConfidenceLevel
    target_id: str
    target_version: str
    applicable_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.claim_id, "claim_id")
        if not self.statement.strip():
            raise ValueError("a reasoning claim requires a non-empty statement")
        validate_stable_identifier(self.target_id, "target_id")
        if not self.target_version.strip():
            raise ValueError("a reasoning claim requires a target version")
        if self.applicable_at.tzinfo is None:
            raise ValueError("applicable_at must be timezone-aware")

    @property
    def has_missing_critical_evidence(self) -> bool:
        """SS14: "missing critical evidence triggers safe next-check guidance or an
        insufficient-evidence result." A claim can still be *constructed* without evidence --
        unlike a malformed field, this is a real, reportable state
        `evaluate_reasoning_claim` surfaces, not a construction-time error."""
        return self.claim_type in _EVIDENCE_REQUIRED_CLAIM_TYPES and not self.evidence_references

    @property
    def has_causal_language(self) -> bool:
        """SS14: "correlation, recent change, shared dependency, or historical similarity is not
        labeled causation alone." A FACT claim is exempt -- an established fact may legitimately
        state a real, confirmed causal relationship; every weaker claim type may not phrase
        itself that way."""
        if self.claim_type is ClaimType.FACT:
            return False
        return bool(_CAUSAL_LANGUAGE.search(self.statement))


class ReasoningOutcome(StrEnum):
    CLAIM_VALID = "claim_valid"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CAUSAL_LANGUAGE_FLAGGED = "causal_language_flagged"


def evaluate_reasoning_claim(claim: ReasoningClaim) -> ReasoningOutcome:
    """Missing critical evidence is checked first: a fact, calculation, or correlation claim
    with no evidence at all is unusable regardless of how it is phrased, so there is no reason to
    also report a causal-language finding on top of it."""
    if claim.has_missing_critical_evidence:
        return ReasoningOutcome.INSUFFICIENT_EVIDENCE
    if claim.has_causal_language:
        return ReasoningOutcome.CAUSAL_LANGUAGE_FLAGGED
    return ReasoningOutcome.CLAIM_VALID
