"""ATLAS-046 SS9/SS23: evidence access and progressive inspection.

Reuses `guardrails.domain.input_guardrails.detect_secret_patterns` for SS23's "secrets, private
keys, tokens, and raw credential-bearing content are prohibited" rather than a third
implementation of the same detection (input guardrails and output guardrails already each reuse
it once).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier


class EvidenceInspectionLevel(StrEnum):
    """SS9's five progressive levels."""

    LABEL = "label"
    EXCERPT = "excerpt"
    CONTEXT = "context"
    ORIGINAL_ARTIFACT = "original_artifact"
    RELATED_EVIDENCE = "related_evidence"


_LEVEL_ORDER: tuple[EvidenceInspectionLevel, ...] = (
    EvidenceInspectionLevel.LABEL,
    EvidenceInspectionLevel.EXCERPT,
    EvidenceInspectionLevel.CONTEXT,
    EvidenceInspectionLevel.ORIGINAL_ARTIFACT,
    EvidenceInspectionLevel.RELATED_EVIDENCE,
)


@dataclass(frozen=True, slots=True)
class EvidenceAccessGrant:
    """What the current, rechecked authorization actually permits for one piece of evidence --
    SS8: "evidence links open only after current authorization.\""""

    evidence_reference: str
    organization_id: str
    environment_id: str
    maximum_permitted_level: EvidenceInspectionLevel
    original_artifact_permitted: bool

    def __post_init__(self) -> None:
        if not self.evidence_reference.strip():
            raise ValueError("an evidence access grant requires a non-empty reference")
        validate_stable_identifier(self.organization_id, "organization_id")
        validate_stable_identifier(self.environment_id, "environment_id")


def is_inspection_permitted(
    *, requested_level: EvidenceInspectionLevel, grant: EvidenceAccessGrant
) -> bool:
    """A level is permitted only up to (and including) the grant's own maximum -- never beyond,
    regardless of what a caller requests. `ORIGINAL_ARTIFACT` additionally requires the grant's
    explicit `original_artifact_permitted` flag (SS9: "it does not expose entire restricted
    documents merely to support one claim" -- a stricter, separate gate from the ordinary level
    order, since a grant could otherwise imply original-artifact access just by being the
    highest-numbered level)."""
    if (
        requested_level is EvidenceInspectionLevel.ORIGINAL_ARTIFACT
        and not grant.original_artifact_permitted
    ):
        return False
    return _LEVEL_ORDER.index(requested_level) <= _LEVEL_ORDER.index(grant.maximum_permitted_level)


def filter_authorized_evidence(
    references: tuple[str, ...],
    *,
    grants: dict[str, EvidenceAccessGrant],
    requesting_organization_id: str,
    requesting_environment_id: str,
) -> tuple[str, ...]:
    """SS23: "explanation is filtered by current user, purpose, and scope." A reference with no
    matching grant -- unauthorized, or simply absent from the grant map -- is silently excluded,
    never surfaced as an error (SS23: counts, labels, and error messages must not leak hidden
    data by revealing that something restricted exists)."""
    return tuple(
        reference
        for reference in references
        if (grant := grants.get(reference)) is not None
        and grant.organization_id == requesting_organization_id
        and grant.environment_id == requesting_environment_id
    )


def contains_prohibited_content(text: str) -> bool:
    return bool(detect_secret_patterns(text))
