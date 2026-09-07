"""ATLAS-022 SS9/SS26: the "Draft" and "Superseded" project lifecycle states.

SS9's lifecycle table names eleven states, but `McpBuilderProject.__post_init__` structurally
ties `BuilderProjectState` to computed analysis evidence -- a project can only be constructed as
`ANALYZED` or `NEEDS_CLARIFICATION`, since every other field (capability candidates, findings,
`analyzed_at`, ...) requires analysis to have already run. "Draft" ("sources and requirements are
being assembled") describes a *pre-analysis* project that has none of that evidence yet, and
"Superseded" ("a newer Builder project version replaces it") describes a relationship between two
already-analyzed projects, not a property either one holds alone. Neither fits inside
`BuilderProjectState` without either loosening `McpBuilderProject`'s real validation or adding an
enum member nothing can ever construct -- so both are modeled here as their own real, independent
types instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class BuilderProjectDraft:
    """SS9: "Draft -- Sources and requirements are being assembled." Exists only until analysis
    produces a real `McpBuilderProject`; carries no analysis evidence itself."""

    draft_id: str
    organization_id: str
    environment_id: str
    owner_id: str
    vendor: str
    product: str
    target_environment: str
    notes: str
    created_at: datetime
    updated_at: datetime
    analyzed_project_id: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.draft_id, "draft_id"),
            (self.organization_id, "organization_id"),
            (self.environment_id, "environment_id"),
            (self.owner_id, "owner_id"),
        ):
            validate_stable_identifier(value, name)
        if (
            not self.vendor.strip()
            or not self.product.strip()
            or not self.target_environment.strip()
        ):
            raise ValueError("a Builder project draft requires vendor, product, and target")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("Builder project draft timestamps must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("a draft cannot be updated before it was created")

    @property
    def is_assembling(self) -> bool:
        return self.analyzed_project_id is None


@dataclass(frozen=True, slots=True)
class BuilderProjectSupersession:
    """SS9/SS26: "Superseded -- A newer Builder project version replaces it." A relationship
    between two distinct, already-analyzed projects."""

    supersession_id: str
    superseded_project_id: str
    superseding_project_id: str
    reason: str
    recorded_by: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.supersession_id, "supersession_id"),
            (self.superseded_project_id, "superseded_project_id"),
            (self.superseding_project_id, "superseding_project_id"),
            (self.recorded_by, "recorded_by"),
        ):
            validate_stable_identifier(value, name)
        if self.superseded_project_id == self.superseding_project_id:
            raise ValueError("a Builder project cannot supersede itself")
        if not self.reason.strip():
            raise ValueError("a Builder project supersession requires a reason")
        if self.recorded_at.tzinfo is None:
            raise ValueError("Builder project supersession time must be timezone-aware")


def a_builder_project_supersedes_itself() -> bool:
    """SS26: superseding is a relationship between two distinct projects.
    `BuilderProjectSupersession` makes a self-referential supersession unconstructable."""
    return False
