"""ATLAS-047 SS13: retrieval guardrails.

`filter_authorized_sources` is the load-bearing function here: it runs before any candidate ever
becomes a visible result, so an unauthorized or excluded-lifecycle document's title, count,
snippet, or mere existence never reaches a downstream caller (SS13: "hidden documents cannot leak
through titles, counts, snippets, embeddings, or timing"). There is no separate redaction step
after the fact -- filtering happens at the one point where leakage would otherwise start.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class SourceLifecycleState(StrEnum):
    ACTIVE = "active"
    MALICIOUS = "malicious"
    QUARANTINED = "quarantined"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    DELETED = "deleted"


_EXCLUDED_LIFECYCLE_STATES = frozenset(
    {
        SourceLifecycleState.MALICIOUS,
        SourceLifecycleState.QUARANTINED,
        SourceLifecycleState.SUSPENDED,
        SourceLifecycleState.EXPIRED,
        SourceLifecycleState.DELETED,
    }
)


@dataclass(frozen=True, slots=True)
class RetrievalSource:
    """SS13: "sources use trust, authority, applicability, freshness, and lifecycle
    metadata.\""""

    source_id: str
    trust: str
    authority: str
    applicability: str
    freshness: str
    lifecycle_state: SourceLifecycleState
    authorized_organization_ids: frozenset[str]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.source_id, "source_id")
        if not self.trust.strip():
            raise ValueError("a retrieval source requires a trust value")
        if not self.authority.strip():
            raise ValueError("a retrieval source requires an authority value")
        if not self.applicability.strip():
            raise ValueError("a retrieval source requires an applicability value")
        if not self.freshness.strip():
            raise ValueError("a retrieval source requires a freshness value")

    @property
    def is_excluded_by_lifecycle(self) -> bool:
        return self.lifecycle_state in _EXCLUDED_LIFECYCLE_STATES

    def is_authorized_for(self, organization_id: str) -> bool:
        return organization_id in self.authorized_organization_ids


def filter_authorized_sources(
    sources: tuple[RetrievalSource, ...], *, organization_id: str
) -> tuple[RetrievalSource, ...]:
    return tuple(
        source
        for source in sources
        if source.is_authorized_for(organization_id) and not source.is_excluded_by_lifecycle
    )


@dataclass(frozen=True, slots=True)
class RetrievalLimits:
    max_breadth: int
    max_depth: int
    max_results: int

    def __post_init__(self) -> None:
        if self.max_breadth < 1:
            raise ValueError("max_breadth must be positive")
        if self.max_depth < 0:
            raise ValueError("max_depth must not be negative")
        if self.max_results < 1:
            raise ValueError("max_results must be positive")


def bounded_retrieval(
    authorized_sources: tuple[RetrievalSource, ...], *, limits: RetrievalLimits
) -> tuple[RetrievalSource, ...]:
    """SS13: "retrieval breadth ... and result size are bounded." Depth (related-document
    expansion) is a caller concern this pure selection function cannot itself enforce without
    knowing the expansion graph -- `limits.max_depth` is a documented budget a caller's own
    expansion logic must respect, not something checkable here."""
    return authorized_sources[: min(limits.max_breadth, limits.max_results)]


@dataclass(frozen=True, slots=True)
class Citation:
    """SS13: "citation targets must exist, support the claim, and remain accessible to the
    user.\" existence is represented by `target_reference` being non-empty -- a real
    existence check against the actual store is a caller concern, this type only carries the
    three checkable facts SS13 names."""

    citation_id: str
    target_reference: str
    supports_claim: bool
    accessible_to_user: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.citation_id, "citation_id")
        if not self.target_reference.strip():
            raise ValueError("a citation requires a target reference")

    @property
    def is_valid(self) -> bool:
        return self.supports_claim and self.accessible_to_user


def invalid_citations(citations: tuple[Citation, ...]) -> tuple[Citation, ...]:
    """Returns only the citations SS13 says must not be presented -- those whose target does not
    support the claim, or is not accessible to the requesting user."""
    return tuple(citation for citation in citations if not citation.is_valid)
