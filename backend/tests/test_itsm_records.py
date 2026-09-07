from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.itsm.domain.records import (
    ApprovalRecord,
    ChangeRecord,
    ConfigurationItemRecord,
    IncidentRecord,
    ItsmRecordCommonFields,
    ItsmRecordType,
    ProblemRecord,
    TaskRecord,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _common(record_type: ItsmRecordType, **overrides: object) -> ItsmRecordCommonFields:
    defaults: dict[str, object] = {
        "integration_reference": "integration.example-001",
        "profile_id": "profile.example-001",
        "external_system": "service_now.example",
        "external_instance": "instance.prod",
        "record_type": record_type,
        "external_record_id": "external.rec-001",
        "display_number": "INC0010001",
        "title": "Example ticket",
        "sanitized_summary": "Sanitized summary text.",
        "state": "open",
        "priority": "P2",
        "impact": "medium",
        "urgency": "medium",
        "severity": "medium",
        "assignment_group": "group.storage",
        "owner_reference": "subject.owner",
        "requester_reference": "subject.requester",
        "approver_reference": None,
        "service_reference": "service.storage",
        "configuration_item_reference": "ci.example-001",
        "environment_id": "environment.prod",
        "site_id": "site.primary",
        "organizational_scope": "org.example",
        "created_at": NOW,
        "updated_at": NOW,
        "resolved_at": None,
        "closed_at": None,
        "planned_start_at": None,
        "planned_end_at": None,
        "classification": DataClassification.INTERNAL,
        "access_policy_reference": "access-policy.example-001",
        "retention_reference": "retention.example-001",
        "external_version": "external-version.1",
        "last_synchronized_at": NOW,
        "last_synchronization_status": "current",
    }
    defaults.update(overrides)
    return ItsmRecordCommonFields(**defaults)  # type: ignore[arg-type]


def test_common_fields_reject_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _common(ItsmRecordType.INCIDENT, created_at=datetime(2026, 9, 7, 12, 0))


def test_common_fields_reject_update_before_creation() -> None:
    with pytest.raises(ValueError, match="cannot update before"):
        _common(
            ItsmRecordType.INCIDENT,
            created_at=NOW,
            updated_at=datetime(2026, 9, 6, 12, 0, tzinfo=UTC),
        )


def test_common_fields_reject_inverted_planned_window() -> None:
    with pytest.raises(ValueError, match="cannot end before it starts"):
        _common(
            ItsmRecordType.INCIDENT,
            planned_start_at=NOW,
            planned_end_at=datetime(2026, 9, 6, 12, 0, tzinfo=UTC),
        )


def test_incident_record_builds() -> None:
    incident = IncidentRecord(
        common=_common(ItsmRecordType.INCIDENT),
        detection_source="atlas.health_checks",
        first_observed_at=NOW,
        symptoms="Elevated latency on the storage service.",
        affected_services=("service.storage",),
        current_impact_summary="Degraded, not down.",
        evidence_references=("evidence.example-001",),
        investigation_references=("investigation.example-001",),
        probable_causes=("disk saturation",),
        probable_cause_confidence="medium",
        workaround_summary=None,
        remediation_recommendation_reference="recommendation.example-001",
        current_status_summary="under investigation",
        resolution_summary=None,
        confirmed_cause=None,
        validation_outcome=None,
    )
    assert incident.common.record_type is ItsmRecordType.INCIDENT


def test_incident_record_rejects_mismatched_common_record_type() -> None:
    with pytest.raises(ValueError, match="requires INCIDENT common fields"):
        IncidentRecord(
            common=_common(ItsmRecordType.CHANGE),
            detection_source="atlas.health_checks",
            first_observed_at=NOW,
            symptoms="symptoms",
            affected_services=(),
            current_impact_summary="summary",
            evidence_references=(),
            investigation_references=(),
            probable_causes=(),
            probable_cause_confidence=None,
            workaround_summary=None,
            remediation_recommendation_reference=None,
            current_status_summary="status",
            resolution_summary=None,
            confirmed_cause=None,
            validation_outcome=None,
        )


def test_problem_record_builds() -> None:
    problem = ProblemRecord(
        common=_common(ItsmRecordType.PROBLEM),
        related_incident_references=("incident.example-001",),
        trend_evidence_references=("evidence.example-001",),
        known_error=True,
        confirmed_root_cause="firmware defect",
        permanent_fix_recommendation_reference="recommendation.example-002",
        risk_summary="Recurring outage risk without a firmware update.",
        owner_reference="subject.owner",
        review_status="under_review",
        linked_change_references=(),
        verification_outcome=None,
    )
    assert problem.common.record_type is ItsmRecordType.PROBLEM


def test_change_record_builds() -> None:
    change = ChangeRecord(
        common=_common(ItsmRecordType.CHANGE),
        change_type="standard",
        risk_summary="Low risk, reversible.",
        affected_services=("service.storage",),
        target_scope="target.example",
        proposed_plan_reference="plan.example-001",
        atlas_recommendation_version="recommendation.example-001.v1",
        preconditions=("backup verified",),
        expected_duration_minutes=30,
        expected_interruption_summary="Brief failover interruption.",
        validation_plan_reference="validation-plan.example-001",
        rollback_plan_reference="rollback-plan.example-001",
        planned_window_start_at=NOW,
        planned_window_end_at=datetime(2026, 9, 7, 13, 0, tzinfo=UTC),
        freeze_constraint_reference=None,
        itsm_approval_state="approved",
        approver_references=("subject.approver",),
        implementation_summary=None,
        recovery_summary=None,
        actual_impact_summary=None,
        review_outcome=None,
    )
    assert change.common.record_type is ItsmRecordType.CHANGE


def test_change_record_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError, match="positive expected duration"):
        ChangeRecord(
            common=_common(ItsmRecordType.CHANGE),
            change_type="standard",
            risk_summary="risk",
            affected_services=(),
            target_scope="target.example",
            proposed_plan_reference="plan.example-001",
            atlas_recommendation_version="recommendation.example-001.v1",
            preconditions=(),
            expected_duration_minutes=0,
            expected_interruption_summary="none",
            validation_plan_reference="validation-plan.example-001",
            rollback_plan_reference="rollback-plan.example-001",
            planned_window_start_at=NOW,
            planned_window_end_at=datetime(2026, 9, 7, 13, 0, tzinfo=UTC),
            freeze_constraint_reference=None,
            itsm_approval_state="approved",
            approver_references=(),
            implementation_summary=None,
            recovery_summary=None,
            actual_impact_summary=None,
            review_outcome=None,
        )


def test_task_record_builds() -> None:
    task = TaskRecord(
        common=_common(ItsmRecordType.TASK),
        parent_record_reference="change.example-001",
        ordered_purpose="pre-implementation validation",
        assigned_group_or_subject="group.storage",
        required_evidence=("backup verification",),
        completion_criteria="backup verified and logged",
        due_at=NOW,
        completion_record_reference=None,
        comments=(),
    )
    assert task.common.record_type is ItsmRecordType.TASK


def test_approval_record_builds() -> None:
    approval = ApprovalRecord(
        common=_common(ItsmRecordType.APPROVAL),
        parent_record_reference="change.example-001",
        approval_question="Approve the proposed failover window?",
        eligible_approver_scope="role.change-approver",
        decision="approved",
        decision_reason="risk acceptable",
        decided_at=NOW,
    )
    assert approval.decision == "approved"


def test_approval_record_requires_decision_fields_together() -> None:
    with pytest.raises(ValueError, match="together"):
        ApprovalRecord(
            common=_common(ItsmRecordType.APPROVAL),
            parent_record_reference="change.example-001",
            approval_question="Approve?",
            eligible_approver_scope="role.change-approver",
            decision="approved",
            decision_reason=None,
            decided_at=None,
        )


def test_configuration_item_record_builds() -> None:
    ci = ConfigurationItemRecord(
        common=_common(ItsmRecordType.CONFIGURATION_ITEM),
        external_ci_class="storage_array",
        ci_name="array-01",
        ci_owner_reference="subject.owner",
        ci_lifecycle_state="in_production",
        ci_criticality="high",
        support_group="group.storage",
        mapped_atlas_entity_id="entity.array-01",
        mapping_confidence=0.92,
        observed_at=NOW,
        review_state="matched",
    )
    assert ci.mapping_confidence == 0.92


def test_configuration_item_requires_entity_and_confidence_together() -> None:
    with pytest.raises(ValueError, match="entity and a confidence"):
        ConfigurationItemRecord(
            common=_common(ItsmRecordType.CONFIGURATION_ITEM),
            external_ci_class="storage_array",
            ci_name="array-01",
            ci_owner_reference="subject.owner",
            ci_lifecycle_state="in_production",
            ci_criticality="high",
            support_group="group.storage",
            mapped_atlas_entity_id="entity.array-01",
            mapping_confidence=None,
            observed_at=NOW,
            review_state="matched",
        )
