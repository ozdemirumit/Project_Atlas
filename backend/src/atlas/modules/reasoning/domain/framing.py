"""ATLAS-041 SS8: problem framing.

Reuses `atlas.core.capabilities.CapabilityClass` for the capability-class ceiling and this
module's own `ConfidenceCategory` (slice 2) for required confidence, rather than new enums.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reasoning.domain.claims import ConfidenceCategory


class UrgencyLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class FramingAmbiguityKind(StrEnum):
    """SS8: "ambiguous target identity, mixed environments, or incompatible time windows are
    resolved or disclosed before analysis.\""""

    AMBIGUOUS_TARGET_IDENTITY = "ambiguous_target_identity"
    MIXED_ENVIRONMENTS = "mixed_environments"
    INCOMPATIBLE_TIME_WINDOWS = "incompatible_time_windows"


@dataclass(frozen=True, slots=True)
class FramingAmbiguityDisclosure:
    kind: FramingAmbiguityKind
    disclosure: str

    def __post_init__(self) -> None:
        if not self.disclosure.strip():
            raise ValueError("a framing ambiguity disclosure requires text")


@dataclass(frozen=True, slots=True)
class ProblemFrame:
    """SS8's nine declared elements, plus `ambiguity_disclosures` giving "resolved or disclosed
    before analysis" a real, populated home rather than an unstated convention."""

    frame_id: str
    question: str
    desired_decision: str
    target_ids: tuple[str, ...]
    business_service_ids: tuple[str, ...]
    environment_id: str
    site_id: str | None
    organizational_boundary: str
    symptom: str
    expected_state: str
    actual_state: str
    first_known_time: datetime
    analysis_window_start: datetime
    analysis_window_end: datetime
    timezone: str
    current_impact: str
    urgency: UrgencyLevel
    available_evidence_classes: tuple[str, ...]
    inaccessible_evidence_classes: tuple[str, ...]
    required_freshness_seconds: int
    required_confidence: ConfidenceCategory
    capability_class_ceiling: CapabilityClass
    success_conditions: tuple[str, ...]
    stopping_conditions: tuple[str, ...]
    ambiguity_disclosures: tuple[FramingAmbiguityDisclosure, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.frame_id, "frame_id")
        validate_stable_identifier(self.environment_id, "environment_id")
        if not self.question.strip():
            raise ValueError("a problem frame requires the user's question")
        if not self.desired_decision.strip():
            raise ValueError("a problem frame requires the desired decision")
        if not self.target_ids:
            raise ValueError("a problem frame requires at least one target")
        if not self.organizational_boundary.strip():
            raise ValueError("a problem frame requires an organizational boundary")
        if not self.symptom.strip():
            raise ValueError("a problem frame requires a symptom")
        if not self.expected_state.strip() or not self.actual_state.strip():
            raise ValueError("a problem frame requires both expected and actual state")
        if self.first_known_time.tzinfo is None:
            raise ValueError("first_known_time must be timezone-aware")
        if self.analysis_window_start.tzinfo is None or self.analysis_window_end.tzinfo is None:
            raise ValueError("the analysis window must be timezone-aware")
        if self.analysis_window_end < self.analysis_window_start:
            raise ValueError("analysis_window_end must not precede analysis_window_start")
        if not self.timezone.strip():
            raise ValueError("a problem frame requires a timezone")
        if not self.current_impact.strip():
            raise ValueError("a problem frame requires the current impact")
        if self.required_freshness_seconds < 1:
            raise ValueError("required_freshness_seconds must be positive")
        if not self.success_conditions:
            raise ValueError("a problem frame requires at least one success condition")
        if not self.stopping_conditions:
            raise ValueError("a problem frame requires at least one stopping condition")

    @property
    def has_disclosed_ambiguity(self) -> bool:
        return bool(self.ambiguity_disclosures)
