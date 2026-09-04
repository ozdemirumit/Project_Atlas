"""ATLAS-046 SS20: investigation presentation.

A read-model reusing this subsystem's own `ExplanationClaim`/`EvidenceLink` for the claim ledger
and evidence filters rather than inventing parallel types. Diagnostic checks, topology, and
related-artifact references are modeled here as plain identifiers/summaries -- a full binding to
the real `health_checks` and `graph` domain objects belongs to the eventual investigation
rendering pipeline (not yet built), not to this presentation-shape slice.

SS20's "users can challenge a claim, add evidence, or mark a mapping issue without modifying
source records" is given real teeth by `InvestigationAnnotation`: it carries a `claim_id`
reference, never a mutation of the claim itself, plus its own separate `annotation_id`/
`recorded_by`/`recorded_at` -- structurally, there is no field through which recording an
annotation could touch source-record state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.explainability.domain.models import EvidenceLink, ExplanationClaim
from atlas.modules.identity.domain.models import validate_stable_identifier


class ClockQuality(StrEnum):
    """SS20: "timeline with source and clock quality.\""""

    AUTHORITATIVE = "authoritative"
    SYNCHRONIZED = "synchronized"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    occurred_at: datetime
    source: str
    clock_quality: ClockQuality
    description: str

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("a timeline entry's occurred_at must be timezone-aware")
        if not self.source.strip():
            raise ValueError("a timeline entry requires a source")
        if not self.description.strip():
            raise ValueError("a timeline entry requires a description")


@dataclass(frozen=True, slots=True)
class TopologyImpact:
    """SS20: "affected and unaffected topology.\""""

    affected_target_ids: tuple[str, ...]
    unaffected_target_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        overlap = set(self.affected_target_ids) & set(self.unaffected_target_ids)
        if overlap:
            raise ValueError(f"a target cannot be both affected and unaffected: {sorted(overlap)}")


@dataclass(frozen=True, slots=True)
class DiagnosticCheckResult:
    """SS20: "diagnostic checks and results.\""""

    check_id: str
    passed: bool
    summary: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.check_id, "check_id")
        if not self.summary.strip():
            raise ValueError("a diagnostic check result requires a summary")


@dataclass(frozen=True, slots=True)
class VersionComparison:
    """SS20: "version comparison and human corrections.\""""

    artifact_id: str
    previous_version: str
    current_version: str
    human_corrections: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.artifact_id, "artifact_id")
        if not self.previous_version.strip() or not self.current_version.strip():
            raise ValueError("a version comparison requires both a previous and current version")


class RelatedArtifactKind(StrEnum):
    """SS20: "related incidents, changes, runbooks, and recommendations.\""""

    INCIDENT = "incident"
    CHANGE = "change"
    RUNBOOK = "runbook"
    RECOMMENDATION = "recommendation"


@dataclass(frozen=True, slots=True)
class RelatedArtifact:
    kind: RelatedArtifactKind
    artifact_id: str
    summary: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.artifact_id, "artifact_id")
        if not self.summary.strip():
            raise ValueError("a related artifact requires a summary")


@dataclass(frozen=True, slots=True)
class EvidenceFilterCriteria:
    source: str | None = None
    target_id: str | None = None
    observed_after: datetime | None = None
    observed_before: datetime | None = None
    authority: str | None = None
    only_conflicting: bool = False


def _conflicting_evidence_references(claims: tuple[ExplanationClaim, ...]) -> frozenset[str]:
    references: set[str] = set()
    for claim in claims:
        if claim.has_contradicting_evidence:
            references.update(claim.evidence_references)
            references.update(claim.contradicting_evidence_references)
    return frozenset(references)


def filter_evidence_for_investigation(
    evidence_links: tuple[EvidenceLink, ...],
    claims: tuple[ExplanationClaim, ...],
    *,
    criteria: EvidenceFilterCriteria,
) -> tuple[EvidenceLink, ...]:
    """SS20: "evidence filters by source, target, time, authority, and conflict." "Conflict" means
    evidence tied to a claim that has contradicting evidence -- both the claim's own supporting
    references and the contradicting ones, since both sides of a contradiction are relevant to a
    reviewer filtering for it."""
    conflicting = _conflicting_evidence_references(claims) if criteria.only_conflicting else None
    filtered = []
    for link in evidence_links:
        if criteria.source is not None and link.source != criteria.source:
            continue
        if criteria.target_id is not None and link.target_id != criteria.target_id:
            continue
        if criteria.observed_after is not None and link.observed_at < criteria.observed_after:
            continue
        if criteria.observed_before is not None and link.observed_at > criteria.observed_before:
            continue
        if criteria.authority is not None and link.authority != criteria.authority:
            continue
        if conflicting is not None and link.reference not in conflicting:
            continue
        filtered.append(link)
    return tuple(filtered)


class InvestigationAnnotationKind(StrEnum):
    """SS20: "challenge a claim, add evidence, or mark a mapping issue.\""""

    CLAIM_CHALLENGE = "claim_challenge"
    EVIDENCE_ADDITION = "evidence_addition"
    MAPPING_ISSUE = "mapping_issue"


@dataclass(frozen=True, slots=True)
class InvestigationAnnotation:
    annotation_id: str
    kind: InvestigationAnnotationKind
    claim_id: str | None
    recorded_by: str
    recorded_at: datetime
    note: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.annotation_id, "annotation_id")
        if self.claim_id is not None:
            validate_stable_identifier(self.claim_id, "claim_id")
        if not self.recorded_by.strip():
            raise ValueError("an investigation annotation requires who recorded it")
        if self.recorded_at.tzinfo is None:
            raise ValueError("an investigation annotation's recorded_at must be timezone-aware")
        if not self.note.strip():
            raise ValueError("an investigation annotation requires a note")
        if self.kind is InvestigationAnnotationKind.CLAIM_CHALLENGE and self.claim_id is None:
            raise ValueError("a claim-challenge annotation requires the claim_id being challenged")


@dataclass(frozen=True, slots=True)
class InvestigationPresentation:
    """SS20's investigation view, aggregating what this subsystem already models plus the
    lightweight presentation-shape types defined above."""

    timeline: tuple[TimelineEntry, ...]
    topology: TopologyImpact
    claims: tuple[ExplanationClaim, ...]
    diagnostic_results: tuple[DiagnosticCheckResult, ...]
    version_comparisons: tuple[VersionComparison, ...]
    related_artifacts: tuple[RelatedArtifact, ...]
    annotations: tuple[InvestigationAnnotation, ...]
