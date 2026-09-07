"""ATLAS-035 SS18/SS21: SIEM-originated ITSM handoff summary and service metrics.

ATLAS-036 governs the actual ticket operations; this module models only the fields SS18 says a
SIEM-originated handoff includes, which ATLAS-036 consumes as its input.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.security_export.domain.detection_content import DetectionUseCaseId
from atlas.modules.security_export.domain.models import SecuritySeverity


class TriageStatus(StrEnum):
    NEW = "new"
    UNDER_REVIEW = "under_review"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    RESOLVED = "resolved"


class SiemServiceMetric(StrEnum):
    """SS21's eight service-objective metric categories."""

    SOURCE_TO_EXPORT_AND_ACKNOWLEDGEMENT_LATENCY = "source_to_export_and_acknowledgement_latency"
    DELIVERY_SUCCESS_RETRY_REJECTION_DUPLICATE_QUARANTINE_RATES = (
        "delivery_success_retry_rejection_duplicate_quarantine_rates"
    )
    BACKLOG_AGE_AND_CAPACITY_FORECAST = "backlog_age_and_capacity_forecast"
    MAPPING_COVERAGE_AND_PARSE_SUCCESS = "mapping_coverage_and_parse_success"
    TEST_EVENT_SUCCESS_AND_LAST_VALIDATION_AGE = "test_event_success_and_last_validation_age"
    DETECTION_EVENTS_TRIAGE_OUTCOMES_AND_FALSE_POSITIVE_FEEDBACK = (
        "detection_events_triage_outcomes_and_false_positive_feedback"
    )
    DESTINATION_AUTHENTICATION_AND_CERTIFICATE_HEALTH = (
        "destination_authentication_and_certificate_health"
    )
    EVENT_RANGE_RECONCILIATION_GAP = "event_range_reconciliation_gap"


@dataclass(frozen=True, slots=True)
class SiemIncidentHandoffSummary:
    """SS18's SIEM-originated incident handoff fields."""

    detection_id: DetectionUseCaseId
    detection_version: str
    alert_reference: str
    event_references: tuple[str, ...]
    severity: SecuritySeverity
    confidence: str
    triage_status: TriageStatus
    affected_deployment: str
    affected_services: tuple[str, ...]
    affected_targets: tuple[str, ...]
    investigation_summary: str
    evidence_link_kinds: tuple[str, ...]
    ownership: str
    synchronization_state: str
    ai_generated_summary: bool
    summary_labeled_as_ai_generated: bool

    def __post_init__(self) -> None:
        required_text = (
            self.detection_version,
            self.alert_reference,
            self.confidence,
            self.affected_deployment,
            self.investigation_summary,
            self.ownership,
            self.synchronization_state,
        )
        if not all(value.strip() for value in required_text):
            raise ValueError("a SIEM incident handoff summary requires every narrative field")
        if not self.event_references or not self.evidence_link_kinds:
            raise ValueError("a SIEM incident handoff summary requires event and evidence links")
        if self.ai_generated_summary and not self.summary_labeled_as_ai_generated:
            raise ValueError("an AI-generated handoff summary must be labeled as AI-generated")


def ticket_creation_authorizes_operational_action() -> bool:
    """SS18: "Ticket creation or updates do not authorize operational action.\""""
    return False
