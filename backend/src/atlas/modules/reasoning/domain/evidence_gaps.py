"""ATLAS-041 SS20/SS21: missing/conflicting evidence and deterministic/model responsibilities.

SS20: "does not silently choose the text most convenient to the recommendation" is enforced by
absence -- `EvidenceConflictRecord` has no "selected" or "winning" field at all, only the
independently-preserved `sides`, so nothing in this type can represent a silently-chosen side.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class MissingEvidenceReason(StrEnum):
    """SS20: "whether it is inaccessible, unavailable, stale, failed, or never collected.\""""

    INACCESSIBLE = "inaccessible"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    FAILED = "failed"
    NEVER_COLLECTED = "never_collected"


@dataclass(frozen=True, slots=True)
class MissingEvidenceDisclosure:
    """SS20's five declared elements for missing evidence."""

    description: str
    why_it_matters: str
    reason: MissingEvidenceReason
    weakened_conclusion_ids: tuple[str, ...]
    safest_useful_next_check_reference: str | None
    partial_answer_appropriate: bool

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("a missing-evidence disclosure requires a description")
        if not self.why_it_matters.strip():
            raise ValueError("a missing-evidence disclosure requires why it matters")


@dataclass(frozen=True, slots=True)
class ConflictingEvidenceSide:
    evidence_id: str
    source: str
    applicability: str
    authority: str
    observed_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_id, "evidence_id")
        if not self.source.strip():
            raise ValueError("a conflicting evidence side requires a source")
        if not self.applicability.strip():
            raise ValueError("a conflicting evidence side requires an applicability statement")
        if not self.authority.strip():
            raise ValueError("a conflicting evidence side requires an authority")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class EvidenceConflictRecord:
    """SS20: "preserves each source, applicability, authority, time, and likely reconciliation
    path." At least two sides are required -- a conflict needs two things in tension -- and both
    are kept independently, never collapsed into a single chosen text."""

    conflict_id: str
    sides: tuple[ConflictingEvidenceSide, ...]
    likely_reconciliation_path: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.conflict_id, "conflict_id")
        if len(self.sides) < 2:
            raise ValueError("an evidence conflict requires at least two sides")
        if not self.likely_reconciliation_path.strip():
            raise ValueError("an evidence conflict requires a likely reconciliation path")


class DeterministicServiceKind(StrEnum):
    """SS21's seven deterministic-service responsibilities."""

    AUTHORIZATION_AND_POLICY_EVALUATION = "authorization_and_policy_evaluation"
    SCHEMA_AND_IDENTITY_VALIDATION = "schema_and_identity_validation"
    GRAPH_QUERIES_AND_DECLARED_CALCULATIONS = "graph_queries_and_declared_calculations"
    EVENT_ORDERING_AND_TIMELINE_NORMALIZATION = "event_ordering_and_timeline_normalization"
    EVIDENCE_RETRIEVAL_CITATION_AND_ACCESS_CONTROL = (
        "evidence_retrieval_citation_and_access_control"
    )
    CONFIDENCE_THRESHOLDS_AND_REQUIRED_OUTPUT_GATES = (
        "confidence_thresholds_and_required_output_gates"
    )
    AUDIT_WORKFLOW_STATE_AND_CONNECTOR_DISPATCH = "audit_workflow_state_and_connector_dispatch"


class ModelAssistedResponsibilityKind(StrEnum):
    """SS21's six model-assisted responsibilities."""

    PROBLEM_FRAMING_SUGGESTIONS = "problem_framing_suggestions"
    EVIDENCE_SUMMARIZATION = "evidence_summarization"
    HYPOTHESIS_GENERATION_AND_COMPARISON = "hypothesis_generation_and_comparison"
    IDENTIFICATION_OF_ASSUMPTIONS_CONFLICTS_AND_UNKNOWNS = (
        "identification_of_assumptions_conflicts_and_unknowns"
    )
    PROPOSED_DISCRIMINATING_CHECKS = "proposed_discriminating_checks"
    AUDIENCE_APPROPRIATE_REASONING_SUMMARY = "audience_appropriate_reasoning_summary"


def model_output_can_override_deterministic_result() -> bool:
    """SS21: "model output cannot override deterministic results." Always `False`."""
    return False
