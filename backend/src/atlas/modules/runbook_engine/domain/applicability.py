"""ATLAS-045 SS20: applicability matching."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ApplicabilityFactorKind(StrEnum):
    """SS20's seven named factor groups."""

    PURPOSE_TRIGGER_OR_CATEGORY = "purpose_trigger_or_category"
    VENDOR_AND_VERSION_COMPATIBILITY = "vendor_and_version_compatibility"
    ENVIRONMENT_AND_TOPOLOGY = "environment_and_topology"
    CURRENT_STATE = "current_state"
    ROLE_POLICY_AND_WINDOW = "role_policy_and_window"
    LIFECYCLE_AND_FRESHNESS = "lifecycle_and_freshness"
    SOURCE_AUTHORITY_AND_PRECEDENCE = "source_authority_and_precedence"


class ApplicabilityFactorResult(StrEnum):
    """SS20: "matches show exact, compatible, partial, conflicting, and inapplicable
    factors.\""""

    EXACT = "exact"
    COMPATIBLE = "compatible"
    PARTIAL = "partial"
    CONFLICTING = "conflicting"
    INAPPLICABLE = "inapplicable"


_RESULT_RANK: dict[ApplicabilityFactorResult, int] = {
    ApplicabilityFactorResult.INAPPLICABLE: 0,
    ApplicabilityFactorResult.CONFLICTING: 1,
    ApplicabilityFactorResult.PARTIAL: 2,
    ApplicabilityFactorResult.COMPATIBLE: 3,
    ApplicabilityFactorResult.EXACT: 4,
}


@dataclass(frozen=True, slots=True)
class ApplicabilityFactor:
    kind: ApplicabilityFactorKind
    result: ApplicabilityFactorResult
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation.strip():
            raise ValueError(
                "SS20: text similarity alone cannot establish applicability -- an applicability"
                " factor requires an explanation grounding its result in a real comparison"
            )


@dataclass(frozen=True, slots=True)
class ApplicabilityMatch:
    runbook_id: str
    version_id: str
    target_id: str
    factors: tuple[ApplicabilityFactor, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.runbook_id, "runbook_id")
        validate_stable_identifier(self.version_id, "version_id")
        validate_stable_identifier(self.target_id, "target_id")
        if not self.factors:
            raise ValueError("an applicability match requires at least one evaluated factor")
        kinds = tuple(factor.kind for factor in self.factors)
        if len(set(kinds)) != len(kinds):
            raise ValueError("an applicability match cannot evaluate the same factor kind twice")

    @property
    def overall_result(self) -> ApplicabilityFactorResult:
        """The single worst-ranked factor determines the overall match -- one `CONFLICTING` or
        `INAPPLICABLE` factor makes the whole match unusable regardless of how well every other
        factor scores, and no factor alone can make the whole match `EXACT`."""
        return min(self.factors, key=lambda factor: _RESULT_RANK[factor.result]).result
