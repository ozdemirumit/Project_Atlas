"""ATLAS-035 SS13: Detection Content Contract.

SS24's MVP scope lists the ten baseline detections (SS12) "as portable specifications" -- Atlas
ships the specification, not an executable rule for an unselected vendor SIEM (SS27's open
question "which SIEM platform is the first validated target?" is still unresolved). This module
defines the shape every specification must satisfy; `baseline_detections.py` supplies the ten
real instances.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.security_export.domain.models import SecuritySeverity


class DetectionUseCaseId(StrEnum):
    """SS12's ten baseline detection use cases."""

    SIEM_UC_001 = "SIEM-UC-001"
    SIEM_UC_002 = "SIEM-UC-002"
    SIEM_UC_003 = "SIEM-UC-003"
    SIEM_UC_004 = "SIEM-UC-004"
    SIEM_UC_005 = "SIEM-UC-005"
    SIEM_UC_006 = "SIEM-UC-006"
    SIEM_UC_007 = "SIEM-UC-007"
    SIEM_UC_008 = "SIEM-UC-008"
    SIEM_UC_009 = "SIEM-UC-009"
    SIEM_UC_010 = "SIEM-UC-010"


class DetectionTestFixtureKind(StrEnum):
    """SS13/SS23: every detection needs positive, negative, duplicate, delayed, and
    missing-field fixtures."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    DUPLICATE = "duplicate"
    DELAYED = "delayed"
    MISSING_FIELD = "missing_field"


def generated_detection_logic_is_trusted_without_review() -> bool:
    """SS13: "Generated detection logic is untrusted until reviewed and tested.\""""
    return False


@dataclass(frozen=True, slots=True)
class DetectionTestFixture:
    kind: DetectionTestFixtureKind
    description: str
    expected_outcome: str

    def __post_init__(self) -> None:
        if not self.description.strip() or not self.expected_outcome.strip():
            raise ValueError("a detection test fixture requires a description and an outcome")


@dataclass(frozen=True, slots=True)
class DetectionContentContract:
    """SS13's full detection package shape."""

    detection_id: DetectionUseCaseId
    version: str
    name: str
    purpose: str
    threat_or_compliance_hypothesis: str
    limitations: str
    required_event_types: tuple[str, ...]
    required_fields: tuple[str, ...]
    query_logic_summary: str
    time_window: str
    thresholds: str
    grouping: str
    suppression_behavior: str
    expected_false_positives: str
    tuning_guidance: str
    severity: SecuritySeverity
    escalation_recommendation: str
    investigation_steps: tuple[str, ...]
    evidence_link_kinds: tuple[str, ...]
    test_fixtures: tuple[DetectionTestFixture, ...]
    owner: str
    review_interval_days: int
    supported_schema_versions: tuple[str, ...]
    change_history: tuple[str, ...]

    def __post_init__(self) -> None:
        required_text = (
            self.version,
            self.name,
            self.purpose,
            self.threat_or_compliance_hypothesis,
            self.limitations,
            self.query_logic_summary,
            self.time_window,
            self.thresholds,
            self.grouping,
            self.suppression_behavior,
            self.expected_false_positives,
            self.tuning_guidance,
            self.escalation_recommendation,
            self.owner,
        )
        if not all(value.strip() for value in required_text):
            raise ValueError("a detection content contract requires every narrative field")
        required_groups = (
            self.required_event_types,
            self.required_fields,
            self.investigation_steps,
            self.evidence_link_kinds,
            self.supported_schema_versions,
            self.change_history,
        )
        if not all(group for group in required_groups):
            raise ValueError("a detection content contract requires every declared group")
        if self.review_interval_days < 1:
            raise ValueError("a detection content contract requires a positive review interval")
        present_kinds = {fixture.kind for fixture in self.test_fixtures}
        if present_kinds != set(DetectionTestFixtureKind):
            raise ValueError(
                "a detection content contract requires all five test fixture kinds "
                "(positive, negative, duplicate, delayed, missing_field)"
            )
