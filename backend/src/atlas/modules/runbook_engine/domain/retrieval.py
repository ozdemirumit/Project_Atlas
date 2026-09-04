"""ATLAS-045 SS21: retrieval and selection.

Builds on slice 1's `RunbookLifecycleState` and slice 9's `ApplicabilityMatch` rather than a
second lifecycle or applicability concept.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.runbook_engine.domain.applicability import (
    ApplicabilityFactorResult,
    ApplicabilityMatch,
)
from atlas.modules.runbook_engine.domain.models import RunbookLifecycleState

_HISTORICAL_STATES = frozenset({RunbookLifecycleState.SUPERSEDED, RunbookLifecycleState.RETIRED})
_RESULT_RANK: dict[ApplicabilityFactorResult, int] = {
    ApplicabilityFactorResult.INAPPLICABLE: 0,
    ApplicabilityFactorResult.CONFLICTING: 1,
    ApplicabilityFactorResult.PARTIAL: 2,
    ApplicabilityFactorResult.COMPATIBLE: 3,
    ApplicabilityFactorResult.EXACT: 4,
}


@dataclass(frozen=True, slots=True)
class RunbookCandidate:
    runbook_id: str
    version_id: str
    state: RunbookLifecycleState
    applicability: ApplicabilityMatch
    is_tested: bool
    ai_generated: bool
    is_exact_product_and_version_match: bool
    authority: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.runbook_id, "runbook_id")
        validate_stable_identifier(self.version_id, "version_id")
        if not self.authority.strip():
            raise ValueError("a runbook candidate requires a source authority")


def is_eligible_for_retrieval(
    candidate: RunbookCandidate, *, authorized_runbook_ids: frozenset[str]
) -> bool:
    """SS21: "only authorized runbooks and metadata are returned.\""""
    return candidate.runbook_id in authorized_runbook_ids


def _rank_key(candidate: RunbookCandidate) -> tuple[int, int, int, int]:
    """Higher tuples sort first (descending). Stacks SS21's ranking rules: active candidates
    outrank historical (superseded/retired) ones; published+applicable+tested+human-authored
    candidates outrank generated or stale content; exact product/version matches outrank generic
    guidance; and, within a tier, a better applicability result still outranks a worse one."""
    is_historical = candidate.state in _HISTORICAL_STATES
    published_applicable_tested = (
        candidate.state is RunbookLifecycleState.PUBLISHED
        and candidate.applicability.overall_result
        in (ApplicabilityFactorResult.EXACT, ApplicabilityFactorResult.COMPATIBLE)
        and candidate.is_tested
        and not candidate.ai_generated
    )
    return (
        0 if is_historical else 1,
        1 if published_applicable_tested else 0,
        1 if candidate.is_exact_product_and_version_match else 0,
        _RESULT_RANK[candidate.applicability.overall_result],
    )


def rank_candidates(
    candidates: tuple[RunbookCandidate, ...], *, authorized_runbook_ids: frozenset[str]
) -> tuple[RunbookCandidate, ...]:
    """SS21: "no suitable runbook is a valid result" -- an empty tuple is a legitimate return
    value here, never an error."""
    eligible = tuple(
        candidate
        for candidate in candidates
        if is_eligible_for_retrieval(candidate, authorized_runbook_ids=authorized_runbook_ids)
    )
    return tuple(sorted(eligible, key=_rank_key, reverse=True))


def resolve_pinned_or_ranked(
    *,
    pinned_version_id: str | None,
    candidates: tuple[RunbookCandidate, ...],
    authorized_runbook_ids: frozenset[str],
) -> RunbookCandidate | None:
    """SS21: "a runbook used by an existing plan remains pinned to its exact version." When a
    plan already pins a version, that exact version is returned (if still authorized and present
    among the candidates) instead of re-ranking; otherwise falls back to the top-ranked
    candidate, or `None` when none qualify."""
    if pinned_version_id is not None:
        for candidate in candidates:
            if candidate.version_id == pinned_version_id and is_eligible_for_retrieval(
                candidate, authorized_runbook_ids=authorized_runbook_ids
            ):
                return candidate
        return None
    ranked = rank_candidates(candidates, authorized_runbook_ids=authorized_runbook_ids)
    return ranked[0] if ranked else None


def find_authority_conflicts(
    candidates: tuple[RunbookCandidate, ...],
) -> tuple[tuple[RunbookCandidate, RunbookCandidate], ...]:
    """SS21: "conflicting runbooks are shown with authority and scope differences." Two
    candidates conflict when both are still plausibly applicable (not `INAPPLICABLE`) and come
    from different source authorities -- surfaced as pairs so a reviewer sees exactly which two
    sources disagree, rather than one being silently picked over the other."""
    applicable = [
        candidate
        for candidate in candidates
        if candidate.applicability.overall_result is not ApplicabilityFactorResult.INAPPLICABLE
    ]
    conflicts = []
    for index, first in enumerate(applicable):
        for second in applicable[index + 1 :]:
            if first.authority != second.authority:
                conflicts.append((first, second))
    return tuple(conflicts)
