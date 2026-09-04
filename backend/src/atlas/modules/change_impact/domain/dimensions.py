"""ATLAS-044 SS8: impact dimensions.

`ImpactSeverity` is a new scale, not a reuse of `reasoning.domain.claims.ConfidenceCategory`,
`decision_engine.domain.hypotheses.DecisionConfidenceCategory`, or
`reasoning.domain.quality.QualityRating` -- those all rate how much to trust a claim or evidence
unit; SS8 rates how materially a change affects a dimension, an orthogonal question a change can
score HIGH on with fully confirmed, high-quality evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ImpactDimension(StrEnum):
    """SS8's ten impact dimensions."""

    AVAILABILITY = "availability"
    PERFORMANCE = "performance"
    CAPACITY = "capacity"
    REDUNDANCY = "redundancy"
    DATA = "data"
    SECURITY = "security"
    OPERATIONS = "operations"
    COMPLIANCE = "compliance"
    RECOVERY = "recovery"
    BUSINESS = "business"


class ImpactSeverity(IntEnum):
    """Ordered so the highest material dimensions (SS8) can be selected by comparison."""

    NONE = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    SEVERE = 4


@dataclass(frozen=True, slots=True)
class ImpactDimensionAssessment:
    dimension: ImpactDimension
    severity: ImpactSeverity
    rationale: str
    affected_entity_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.rationale.strip():
            raise ValueError("an impact dimension assessment requires a rationale")
        for entity_id in self.affected_entity_ids:
            validate_stable_identifier(entity_id, "affected_entity_id")


def highest_material_dimensions(
    assessments: tuple[ImpactDimensionAssessment, ...],
) -> tuple[ImpactDimensionAssessment, ...]:
    """SS8: "an overall risk summary preserves the highest material dimensions and rationale."
    A dimension rated NONE is not material and is excluded; among the rest, only the
    highest-severity assessments are kept."""
    material = tuple(a for a in assessments if a.severity is not ImpactSeverity.NONE)
    if not material:
        return ()
    highest = max(a.severity for a in material)
    return tuple(a for a in material if a.severity is highest)
