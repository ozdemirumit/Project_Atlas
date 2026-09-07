"""ATLAS-036 SS5/SS6: the normalized ITSM object model.

ITSM remains authoritative for these records (SS5) -- Atlas caches bounded, versioned snapshots
retrieved through a governed adapter, it does not originate ticket lifecycle, assignment, SLA,
or approval state. `external_version` carries the vendor's own concurrency token so an outbound
update can detect a stale read (SS16).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import validate_stable_identifier


class ItsmRecordType(StrEnum):
    INCIDENT = "incident"
    PROBLEM = "problem"
    CHANGE = "change"
    TASK = "task"
    APPROVAL = "approval"
    CONFIGURATION_ITEM = "configuration_item"


@dataclass(frozen=True, slots=True)
class ItsmRecordCommonFields:
    """SS6.1's fields, shared by every normalized record type."""

    integration_reference: str
    profile_id: str
    external_system: str
    external_instance: str
    record_type: ItsmRecordType
    external_record_id: str
    display_number: str
    title: str
    sanitized_summary: str
    state: str
    priority: str
    impact: str
    urgency: str
    severity: str
    assignment_group: str | None
    owner_reference: str | None
    requester_reference: str | None
    approver_reference: str | None
    service_reference: str | None
    configuration_item_reference: str | None
    environment_id: str
    site_id: str
    organizational_scope: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    classification: DataClassification
    access_policy_reference: str
    retention_reference: str
    external_version: str
    last_synchronized_at: datetime
    last_synchronization_status: str

    def __post_init__(self) -> None:
        for value in (
            self.integration_reference,
            self.profile_id,
            self.external_system,
            self.external_instance,
            self.external_record_id,
            self.environment_id,
            self.site_id,
            self.access_policy_reference,
            self.retention_reference,
            self.external_version,
        ):
            validate_stable_identifier(value, "ITSM record identifier")
        if not self.display_number.strip() or not self.title.strip():
            raise ValueError("an ITSM record requires a display number and title")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("ITSM record times must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("an ITSM record cannot update before it was created")
        if self.last_synchronized_at.tzinfo is None:
            raise ValueError("ITSM synchronization time must be timezone-aware")
        for optional_time in (
            self.resolved_at,
            self.closed_at,
            self.planned_start_at,
            self.planned_end_at,
        ):
            if optional_time is not None and optional_time.tzinfo is None:
                raise ValueError("ITSM record times must be timezone-aware")
        if (
            self.planned_start_at is not None
            and self.planned_end_at is not None
            and self.planned_end_at < self.planned_start_at
        ):
            raise ValueError("an ITSM change window cannot end before it starts")


@dataclass(frozen=True, slots=True)
class IncidentRecord:
    """SS6.2."""

    common: ItsmRecordCommonFields
    detection_source: str
    first_observed_at: datetime
    symptoms: str
    affected_services: tuple[str, ...]
    current_impact_summary: str
    evidence_references: tuple[str, ...]
    investigation_references: tuple[str, ...]
    probable_causes: tuple[str, ...]
    probable_cause_confidence: str | None
    workaround_summary: str | None
    remediation_recommendation_reference: str | None
    current_status_summary: str
    resolution_summary: str | None
    confirmed_cause: str | None
    validation_outcome: str | None

    def __post_init__(self) -> None:
        if self.common.record_type is not ItsmRecordType.INCIDENT:
            raise ValueError("an incident record requires INCIDENT common fields")
        if self.first_observed_at.tzinfo is None:
            raise ValueError("incident first-observed time must be timezone-aware")
        if not self.symptoms.strip() or not self.current_status_summary.strip():
            raise ValueError("an incident record requires symptoms and a current status")


@dataclass(frozen=True, slots=True)
class ProblemRecord:
    """SS6.3."""

    common: ItsmRecordCommonFields
    related_incident_references: tuple[str, ...]
    trend_evidence_references: tuple[str, ...]
    known_error: bool
    confirmed_root_cause: str | None
    permanent_fix_recommendation_reference: str | None
    risk_summary: str
    owner_reference: str
    review_status: str
    linked_change_references: tuple[str, ...]
    verification_outcome: str | None

    def __post_init__(self) -> None:
        if self.common.record_type is not ItsmRecordType.PROBLEM:
            raise ValueError("a problem record requires PROBLEM common fields")
        if not self.risk_summary.strip() or not self.owner_reference.strip():
            raise ValueError("a problem record requires a risk summary and an owner")


@dataclass(frozen=True, slots=True)
class ChangeRecord:
    """SS6.4."""

    common: ItsmRecordCommonFields
    change_type: str
    risk_summary: str
    affected_services: tuple[str, ...]
    target_scope: str
    proposed_plan_reference: str
    atlas_recommendation_version: str
    preconditions: tuple[str, ...]
    expected_duration_minutes: int
    expected_interruption_summary: str
    validation_plan_reference: str
    rollback_plan_reference: str
    planned_window_start_at: datetime
    planned_window_end_at: datetime
    freeze_constraint_reference: str | None
    itsm_approval_state: str
    approver_references: tuple[str, ...]
    implementation_summary: str | None
    recovery_summary: str | None
    actual_impact_summary: str | None
    review_outcome: str | None

    def __post_init__(self) -> None:
        if self.common.record_type is not ItsmRecordType.CHANGE:
            raise ValueError("a change record requires CHANGE common fields")
        if not self.change_type.strip() or not self.risk_summary.strip():
            raise ValueError("a change record requires a change type and risk summary")
        if (
            not self.proposed_plan_reference.strip()
            or not self.atlas_recommendation_version.strip()
        ):
            raise ValueError("a change record requires an immutable Atlas plan reference")
        if self.expected_duration_minutes < 1:
            raise ValueError("a change record requires a positive expected duration")
        if self.planned_window_start_at.tzinfo is None or self.planned_window_end_at.tzinfo is None:
            raise ValueError("a change window must be timezone-aware")
        if self.planned_window_end_at <= self.planned_window_start_at:
            raise ValueError("a change window must end after it starts")


@dataclass(frozen=True, slots=True)
class TaskRecord:
    """SS6.5, task half."""

    common: ItsmRecordCommonFields
    parent_record_reference: str
    ordered_purpose: str
    assigned_group_or_subject: str
    required_evidence: tuple[str, ...]
    completion_criteria: str
    due_at: datetime | None
    completion_record_reference: str | None
    comments: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.common.record_type is not ItsmRecordType.TASK:
            raise ValueError("a task record requires TASK common fields")
        if not self.parent_record_reference.strip() or not self.completion_criteria.strip():
            raise ValueError("a task record requires a parent reference and completion criteria")
        if self.due_at is not None and self.due_at.tzinfo is None:
            raise ValueError("a task due time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    """SS6.5, approval half."""

    common: ItsmRecordCommonFields
    parent_record_reference: str
    approval_question: str
    eligible_approver_scope: str
    decision: str | None
    decision_reason: str | None
    decided_at: datetime | None

    def __post_init__(self) -> None:
        if self.common.record_type is not ItsmRecordType.APPROVAL:
            raise ValueError("an approval record requires APPROVAL common fields")
        if not self.approval_question.strip() or not self.eligible_approver_scope.strip():
            raise ValueError("an approval record requires a question and an eligible scope")
        if self.decided_at is not None and self.decided_at.tzinfo is None:
            raise ValueError("an approval decision time must be timezone-aware")
        decision_fields = (self.decision, self.decision_reason, self.decided_at)
        if any(value is not None for value in decision_fields) and not all(
            value is not None for value in decision_fields
        ):
            raise ValueError("an approval decision requires its outcome, reason, and time together")


@dataclass(frozen=True, slots=True)
class ConfigurationItemRecord:
    """SS6.6."""

    common: ItsmRecordCommonFields
    external_ci_class: str
    ci_name: str
    ci_owner_reference: str
    ci_lifecycle_state: str
    ci_criticality: str
    support_group: str
    mapped_atlas_entity_id: str | None
    mapping_confidence: float | None
    observed_at: datetime
    review_state: str

    def __post_init__(self) -> None:
        if self.common.record_type is not ItsmRecordType.CONFIGURATION_ITEM:
            raise ValueError(
                "a configuration item record requires CONFIGURATION_ITEM common fields"
            )
        if not self.external_ci_class.strip() or not self.ci_name.strip():
            raise ValueError("a configuration item record requires a class and a name")
        if self.observed_at.tzinfo is None:
            raise ValueError("a configuration item observation time must be timezone-aware")
        if self.mapping_confidence is not None and not 0.0 <= self.mapping_confidence <= 1.0:
            raise ValueError("a configuration item mapping confidence must be between 0 and 1")
        if (self.mapped_atlas_entity_id is None) != (self.mapping_confidence is None):
            raise ValueError(
                "a configuration item mapping requires both an entity and a confidence"
            )
