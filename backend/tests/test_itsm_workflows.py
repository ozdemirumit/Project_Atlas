from __future__ import annotations

from itertools import pairwise

import pytest

from atlas.modules.itsm.domain.workflows import (
    ItsmChangeWorkflowStage,
    ItsmIncidentWorkflowStage,
    is_valid_change_transition,
    is_valid_incident_transition,
    itsm_approved_state_is_sufficient_execution_authority,
    ticket_creation_authorizes_infrastructure_action,
)


def test_ticket_creation_never_authorizes_infrastructure_action() -> None:
    assert ticket_creation_authorizes_infrastructure_action() is False


def test_itsm_approved_state_is_never_sufficient_execution_authority() -> None:
    assert itsm_approved_state_is_sufficient_execution_authority() is False


def test_incident_happy_path_is_valid() -> None:
    path = [
        ItsmIncidentWorkflowStage.CONTEXT_DETECTED,
        ItsmIncidentWorkflowStage.DEDUPLICATION_SEARCHED,
        ItsmIncidentWorkflowStage.CURRENT_STATE_RETRIEVED,
        ItsmIncidentWorkflowStage.ANALYSIS_PRODUCED,
        ItsmIncidentWorkflowStage.OUTBOUND_UPDATE_REVIEWED,
        ItsmIncidentWorkflowStage.RECORD_CREATED_OR_UPDATED,
        ItsmIncidentWorkflowStage.SYNCHRONIZATION_RESULT_STORED,
        ItsmIncidentWorkflowStage.LATER_OBSERVATION_APPENDED,
        ItsmIncidentWorkflowStage.RESOLUTION_IMPORTED,
    ]
    for current, target in pairwise(path):
        assert is_valid_incident_transition(current, target)


def test_incident_can_append_multiple_later_observations() -> None:
    assert is_valid_incident_transition(
        ItsmIncidentWorkflowStage.LATER_OBSERVATION_APPENDED,
        ItsmIncidentWorkflowStage.LATER_OBSERVATION_APPENDED,
    )


def test_incident_resolution_imported_is_terminal() -> None:
    for stage in ItsmIncidentWorkflowStage:
        assert not is_valid_incident_transition(
            ItsmIncidentWorkflowStage.RESOLUTION_IMPORTED, stage
        )


def test_incident_cannot_skip_deduplication() -> None:
    assert not is_valid_incident_transition(
        ItsmIncidentWorkflowStage.CONTEXT_DETECTED,
        ItsmIncidentWorkflowStage.CURRENT_STATE_RETRIEVED,
    )


def test_change_happy_path_is_valid() -> None:
    path = [
        ItsmChangeWorkflowStage.RECOMMENDATION_VERSIONED,
        ItsmChangeWorkflowStage.DRAFT_ITSM_CHANGE,
        ItsmChangeWorkflowStage.HUMAN_AND_PROCESS_REVIEW,
        ItsmChangeWorkflowStage.WINDOW_AND_PRECONDITIONS_APPROVED,
        ItsmChangeWorkflowStage.ATLAS_BOUND_APPROVAL,
        ItsmChangeWorkflowStage.REVALIDATED,
        ItsmChangeWorkflowStage.HANDOFF,
        ItsmChangeWorkflowStage.OUTCOME_VERIFIED,
        ItsmChangeWorkflowStage.POST_IMPLEMENTATION_REVIEWED,
    ]
    for current, target in pairwise(path):
        assert is_valid_change_transition(current, target)


def test_change_revalidation_failure_returns_to_review() -> None:
    assert is_valid_change_transition(
        ItsmChangeWorkflowStage.REVALIDATED, ItsmChangeWorkflowStage.HUMAN_AND_PROCESS_REVIEW
    )


def test_change_post_implementation_review_is_terminal() -> None:
    for stage in ItsmChangeWorkflowStage:
        assert not is_valid_change_transition(
            ItsmChangeWorkflowStage.POST_IMPLEMENTATION_REVIEWED, stage
        )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (
            ItsmChangeWorkflowStage.RECOMMENDATION_VERSIONED,
            ItsmChangeWorkflowStage.HANDOFF,
        ),
        (
            ItsmChangeWorkflowStage.WINDOW_AND_PRECONDITIONS_APPROVED,
            ItsmChangeWorkflowStage.HANDOFF,
        ),
    ],
)
def test_change_cannot_skip_atlas_bound_approval(
    current: ItsmChangeWorkflowStage, target: ItsmChangeWorkflowStage
) -> None:
    assert not is_valid_change_transition(current, target)
