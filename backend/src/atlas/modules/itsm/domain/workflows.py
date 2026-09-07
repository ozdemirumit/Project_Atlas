"""ATLAS-036 SS10/SS11: incident and change workflow lifecycles.

Both lifecycles exist to make one thing structurally impossible: treating a ticket state as
execution authority. `itsm_approved_state_is_sufficient_execution_authority` captures SS11's
core point directly; ATLAS-037 remains the actual approval contract.
"""

from __future__ import annotations

from enum import StrEnum


class ItsmIncidentWorkflowStage(StrEnum):
    """SS10's nine-step incident workflow."""

    CONTEXT_DETECTED = "context_detected"
    DEDUPLICATION_SEARCHED = "deduplication_searched"
    CURRENT_STATE_RETRIEVED = "current_state_retrieved"
    ANALYSIS_PRODUCED = "analysis_produced"
    OUTBOUND_UPDATE_REVIEWED = "outbound_update_reviewed"
    RECORD_CREATED_OR_UPDATED = "record_created_or_updated"
    SYNCHRONIZATION_RESULT_STORED = "synchronization_result_stored"
    LATER_OBSERVATION_APPENDED = "later_observation_appended"
    RESOLUTION_IMPORTED = "resolution_imported"


_INCIDENT_TRANSITIONS: dict[ItsmIncidentWorkflowStage, frozenset[ItsmIncidentWorkflowStage]] = {
    ItsmIncidentWorkflowStage.CONTEXT_DETECTED: frozenset(
        {ItsmIncidentWorkflowStage.DEDUPLICATION_SEARCHED}
    ),
    ItsmIncidentWorkflowStage.DEDUPLICATION_SEARCHED: frozenset(
        {ItsmIncidentWorkflowStage.CURRENT_STATE_RETRIEVED}
    ),
    ItsmIncidentWorkflowStage.CURRENT_STATE_RETRIEVED: frozenset(
        {ItsmIncidentWorkflowStage.ANALYSIS_PRODUCED}
    ),
    ItsmIncidentWorkflowStage.ANALYSIS_PRODUCED: frozenset(
        {ItsmIncidentWorkflowStage.OUTBOUND_UPDATE_REVIEWED}
    ),
    ItsmIncidentWorkflowStage.OUTBOUND_UPDATE_REVIEWED: frozenset(
        {ItsmIncidentWorkflowStage.RECORD_CREATED_OR_UPDATED}
    ),
    ItsmIncidentWorkflowStage.RECORD_CREATED_OR_UPDATED: frozenset(
        {ItsmIncidentWorkflowStage.SYNCHRONIZATION_RESULT_STORED}
    ),
    ItsmIncidentWorkflowStage.SYNCHRONIZATION_RESULT_STORED: frozenset(
        {
            ItsmIncidentWorkflowStage.LATER_OBSERVATION_APPENDED,
            ItsmIncidentWorkflowStage.RESOLUTION_IMPORTED,
        }
    ),
    ItsmIncidentWorkflowStage.LATER_OBSERVATION_APPENDED: frozenset(
        {
            ItsmIncidentWorkflowStage.LATER_OBSERVATION_APPENDED,
            ItsmIncidentWorkflowStage.RESOLUTION_IMPORTED,
        }
    ),
    ItsmIncidentWorkflowStage.RESOLUTION_IMPORTED: frozenset(),
}


def is_valid_incident_transition(
    current: ItsmIncidentWorkflowStage,
    target: ItsmIncidentWorkflowStage,
) -> bool:
    return target in _INCIDENT_TRANSITIONS[current]


def ticket_creation_authorizes_infrastructure_action() -> bool:
    """SS10: "Ticket creation does not imply Atlas may act on infrastructure.\""""
    return False


class ItsmChangeWorkflowStage(StrEnum):
    """SS11's nine-node change workflow."""

    RECOMMENDATION_VERSIONED = "recommendation_versioned"
    DRAFT_ITSM_CHANGE = "draft_itsm_change"
    HUMAN_AND_PROCESS_REVIEW = "human_and_process_review"
    WINDOW_AND_PRECONDITIONS_APPROVED = "window_and_preconditions_approved"
    ATLAS_BOUND_APPROVAL = "atlas_bound_approval"
    REVALIDATED = "revalidated"
    HANDOFF = "handoff"
    OUTCOME_VERIFIED = "outcome_verified"
    POST_IMPLEMENTATION_REVIEWED = "post_implementation_reviewed"


_CHANGE_TRANSITIONS: dict[ItsmChangeWorkflowStage, frozenset[ItsmChangeWorkflowStage]] = {
    ItsmChangeWorkflowStage.RECOMMENDATION_VERSIONED: frozenset(
        {ItsmChangeWorkflowStage.DRAFT_ITSM_CHANGE}
    ),
    ItsmChangeWorkflowStage.DRAFT_ITSM_CHANGE: frozenset(
        {ItsmChangeWorkflowStage.HUMAN_AND_PROCESS_REVIEW}
    ),
    ItsmChangeWorkflowStage.HUMAN_AND_PROCESS_REVIEW: frozenset(
        {ItsmChangeWorkflowStage.WINDOW_AND_PRECONDITIONS_APPROVED}
    ),
    ItsmChangeWorkflowStage.WINDOW_AND_PRECONDITIONS_APPROVED: frozenset(
        {ItsmChangeWorkflowStage.ATLAS_BOUND_APPROVAL}
    ),
    ItsmChangeWorkflowStage.ATLAS_BOUND_APPROVAL: frozenset({ItsmChangeWorkflowStage.REVALIDATED}),
    ItsmChangeWorkflowStage.REVALIDATED: frozenset(
        {ItsmChangeWorkflowStage.HANDOFF, ItsmChangeWorkflowStage.HUMAN_AND_PROCESS_REVIEW}
    ),
    ItsmChangeWorkflowStage.HANDOFF: frozenset({ItsmChangeWorkflowStage.OUTCOME_VERIFIED}),
    ItsmChangeWorkflowStage.OUTCOME_VERIFIED: frozenset(
        {ItsmChangeWorkflowStage.POST_IMPLEMENTATION_REVIEWED}
    ),
    ItsmChangeWorkflowStage.POST_IMPLEMENTATION_REVIEWED: frozenset(),
}


def is_valid_change_transition(
    current: ItsmChangeWorkflowStage,
    target: ItsmChangeWorkflowStage,
) -> bool:
    return target in _CHANGE_TRANSITIONS[current]


def itsm_approved_state_is_sufficient_execution_authority() -> bool:
    """SS11: "An ITSM state such as Approved is one required fact, not an execution token.\""""
    return False
