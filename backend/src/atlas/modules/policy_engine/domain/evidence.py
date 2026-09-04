"""ATLAS-025 SS13: evidence conditions.

"Policy does not judge model rhetoric; it evaluates declared structured evidence references" --
this module never inspects free text. `EvidenceReference` is a specific, already-computed claim
some other module (health_checks, graph, backup_operations, ...) stands behind; this module only
decides whether a set of required evidence kinds are present, satisfied, and fresh enough.
Reuses `health_checks.domain.models.FreshnessState` rather than inventing a second freshness
concept for the same idea.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.health_checks.domain.models import FreshnessState


class EvidenceKind(StrEnum):
    """The eight evidence kinds SS13 lists policy may require."""

    TARGET_HEALTH = "target_health"
    GRAPH_FRESHNESS = "graph_freshness"
    BACKUP_OR_PROTECTION_STATUS = "backup_or_protection_status"
    RUNBOOK_COMPATIBILITY = "runbook_compatibility"
    PRECONDITION_CHECK = "precondition_check"
    ROLLBACK_OR_RECOVERY_PLAN = "rollback_or_recovery_plan"
    SERVICE_OWNER_ACKNOWLEDGEMENT = "service_owner_acknowledgement"
    ADDITIONAL_HUMAN_EVIDENCE = "additional_human_evidence"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """One declared, structured claim -- e.g. a health_checks HealthObservation, a graph
    coverage summary, a backup_operations protection-status record -- already resolved
    elsewhere and handed to Policy as a fact, not re-derived here."""

    reference: str
    kind: EvidenceKind
    observed_at: datetime
    freshness: FreshnessState
    satisfied: bool

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValueError("an evidence reference requires a non-empty reference")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    kind: EvidenceKind
    maximum_age_seconds: int

    def __post_init__(self) -> None:
        if self.maximum_age_seconds < 1:
            raise ValueError("maximum_age_seconds must be positive")


@dataclass(frozen=True, slots=True)
class EvidenceConditionResult:
    satisfied: bool
    unmet_requirements: tuple[EvidenceKind, ...]
    stale_references: tuple[str, ...]


def validate_evidence_conditions(
    requirements: tuple[EvidenceRequirement, ...],
    references: tuple[EvidenceReference, ...],
    *,
    now: datetime,
) -> EvidenceConditionResult:
    """A requirement is met only when a reference of the same kind exists, reports itself
    satisfied, is not itself STALE or UNKNOWN (FreshnessState), and was observed within its
    requirement's own maximum age. When more than one reference of the same kind is supplied,
    only the most recently observed one is considered -- a stale earlier reference cannot be
    used to satisfy a requirement a fresher one of the same kind then fails."""
    latest_by_kind: dict[EvidenceKind, EvidenceReference] = {}
    for reference in references:
        current = latest_by_kind.get(reference.kind)
        if current is None or reference.observed_at > current.observed_at:
            latest_by_kind[reference.kind] = reference

    unmet: list[EvidenceKind] = []
    stale: list[str] = []
    for requirement in requirements:
        matched_reference = latest_by_kind.get(requirement.kind)
        if matched_reference is None or not matched_reference.satisfied:
            unmet.append(requirement.kind)
            continue
        age_seconds = (now - matched_reference.observed_at).total_seconds()
        is_too_old = age_seconds < 0 or age_seconds > requirement.maximum_age_seconds
        is_unusable_freshness = matched_reference.freshness in (
            FreshnessState.STALE,
            FreshnessState.UNKNOWN,
        )
        if is_too_old or is_unusable_freshness:
            unmet.append(requirement.kind)
            stale.append(matched_reference.reference)

    return EvidenceConditionResult(
        satisfied=not unmet,
        unmet_requirements=tuple(unmet),
        stale_references=tuple(stale),
    )
