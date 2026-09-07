from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.event_catalog import (
    DOMAIN_EVENT_CATALOG,
    AIRecommendationGenerated,
    ApprovalGranted,
    ApprovalRequestCreated,
    ConnectorCapabilityCompleted,
    ConnectorCapabilityFailed,
    ConnectorCapabilityStarted,
    EventOwner,
    KnowledgeItemPublished,
    WorkflowRunCompleted,
    WorkflowRunFailed,
    WorkflowRunStarted,
    another_component_publishes_an_event_claiming_a_different_owners_authoritative_state,
    event_catalog_entry,
)
from atlas.core.events import is_valid_event_type_name

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def test_ownership_violation_never_happens() -> None:
    assert (
        another_component_publishes_an_event_claiming_a_different_owners_authoritative_state()
        is False
    )


def test_catalog_has_exactly_ten_entries() -> None:
    assert len(DOMAIN_EVENT_CATALOG) == 10


def test_catalog_entries_have_unique_event_types() -> None:
    types = [entry.event_type for entry in DOMAIN_EVENT_CATALOG]
    assert len(set(types)) == len(types)


def test_every_catalog_event_type_follows_the_naming_convention() -> None:
    for entry in DOMAIN_EVENT_CATALOG:
        assert is_valid_event_type_name(entry.event_type)


def test_every_catalog_entry_has_an_owner_and_description() -> None:
    for entry in DOMAIN_EVENT_CATALOG:
        assert entry.owner in EventOwner
        assert entry.description.strip()


def test_event_catalog_entry_looks_up_by_type() -> None:
    entry = event_catalog_entry("WorkflowRunStarted")
    assert entry.owner is EventOwner.WORKFLOWS
    assert entry.payload_type is WorkflowRunStarted


def test_event_catalog_entry_raises_for_unknown_type() -> None:
    with pytest.raises(KeyError):
        event_catalog_entry("SomeUnregisteredEvent")


def test_workflow_run_started_requires_positive_definition_version() -> None:
    with pytest.raises(ValueError, match="definition_version must be positive"):
        WorkflowRunStarted(
            workflow_run_id="workflow-run.example-001",
            definition_id="workflow-definition.example-001",
            definition_version=0,
            triggered_by="subject.example",
            started_at=NOW,
        )


def test_workflow_run_completed_requires_outcome_summary() -> None:
    with pytest.raises(ValueError, match="outcome_summary is required"):
        WorkflowRunCompleted(
            workflow_run_id="workflow-run.example-001",
            definition_id="workflow-definition.example-001",
            completed_at=NOW,
            outcome_summary="  ",
        )


def test_workflow_run_failed_builds() -> None:
    event = WorkflowRunFailed(
        workflow_run_id="workflow-run.example-001",
        definition_id="workflow-definition.example-001",
        failed_at=NOW,
        failure_reason="A precondition failed during execution.",
    )
    assert event.failure_reason


def test_connector_capability_started_requires_all_identity_fields() -> None:
    with pytest.raises(ValueError, match="capability_id is required"):
        ConnectorCapabilityStarted(
            connector_id="connector.example",
            instance_id="connector-instance.example",
            capability_id="",
            capability_class="C1",
            started_at=NOW,
        )


def test_connector_capability_completed_builds() -> None:
    event = ConnectorCapabilityCompleted(
        connector_id="connector.example",
        instance_id="connector-instance.example",
        capability_id="capability.inventory-read",
        completed_at=NOW,
        result_code="capability_succeeded",
    )
    assert event.result_code == "capability_succeeded"


def test_connector_capability_failed_builds() -> None:
    event = ConnectorCapabilityFailed(
        connector_id="connector.example",
        instance_id="connector-instance.example",
        capability_id="capability.inventory-read",
        failed_at=NOW,
        failure_reason="Timed out waiting for a response.",
    )
    assert event.failure_reason


def test_knowledge_item_published_requires_positive_version() -> None:
    with pytest.raises(ValueError, match="version must be positive"):
        KnowledgeItemPublished(
            item_id="knowledge-item.example-001",
            source_draft_id="knowledge-draft.example-001",
            version=0,
            published_at=NOW,
            published_by="subject.example",
        )


def test_approval_request_created_builds() -> None:
    event = ApprovalRequestCreated(
        request_id="approval.example-001",
        packet_version=1,
        requested_by="subject.example",
        created_at=NOW,
    )
    assert event.packet_version == 1


def test_approval_granted_builds() -> None:
    event = ApprovalGranted(
        request_id="approval.example-001",
        decision_id="approval_decision.example-001",
        reviewer_id="subject.reviewer",
        granted_at=NOW,
    )
    assert event.reviewer_id == "subject.reviewer"


def test_ai_recommendation_generated_requires_non_negative_option_count() -> None:
    with pytest.raises(ValueError, match="option_count cannot be negative"):
        AIRecommendationGenerated(
            recommendation_id="recommendation.example-001",
            source_case_id="rca-case.example-001",
            version=1,
            generated_at=NOW,
            option_count=-1,
        )
