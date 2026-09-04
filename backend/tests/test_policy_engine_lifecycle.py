from __future__ import annotations

import pytest

from atlas.modules.policy_engine.domain.lifecycle import (
    PolicyAuthoringSeparationError,
    PolicyLifecycleTransitionError,
    allowed_next_states,
    is_allowed_transition,
    require_allowed_transition,
    require_authoring_separation,
)
from atlas.modules.policy_engine.domain.policy_set import PolicyLifecycleState


def test_draft_may_only_advance_to_validating() -> None:
    assert allowed_next_states(PolicyLifecycleState.DRAFT) == {PolicyLifecycleState.VALIDATING}


def test_validating_can_advance_or_fall_back_to_draft() -> None:
    assert allowed_next_states(PolicyLifecycleState.VALIDATING) == {
        PolicyLifecycleState.SIMULATION,
        PolicyLifecycleState.DRAFT,
    }


def test_review_can_approve_or_send_back_to_draft() -> None:
    assert allowed_next_states(PolicyLifecycleState.REVIEW) == {
        PolicyLifecycleState.APPROVED,
        PolicyLifecycleState.DRAFT,
    }


def test_approved_can_schedule_or_activate_immediately() -> None:
    assert allowed_next_states(PolicyLifecycleState.APPROVED) == {
        PolicyLifecycleState.SCHEDULED,
        PolicyLifecycleState.ACTIVE,
    }


def test_active_can_be_suspended_or_deprecated() -> None:
    assert allowed_next_states(PolicyLifecycleState.ACTIVE) == {
        PolicyLifecycleState.SUSPENDED,
        PolicyLifecycleState.DEPRECATED,
    }


def test_suspended_can_reactivate_or_deprecate() -> None:
    assert allowed_next_states(PolicyLifecycleState.SUSPENDED) == {
        PolicyLifecycleState.ACTIVE,
        PolicyLifecycleState.DEPRECATED,
    }


def test_deprecated_can_only_retire() -> None:
    assert allowed_next_states(PolicyLifecycleState.DEPRECATED) == {PolicyLifecycleState.RETIRED}


def test_retired_is_terminal() -> None:
    assert allowed_next_states(PolicyLifecycleState.RETIRED) == frozenset()


def test_every_state_is_covered_by_the_transition_table() -> None:
    for state in PolicyLifecycleState:
        # Raises KeyError if any state is missing from the table -- this is the safety net that
        # catches a future SS15 state addition nobody wired a transition for.
        allowed_next_states(state)


def test_is_allowed_transition_matches_the_table() -> None:
    assert is_allowed_transition(PolicyLifecycleState.DRAFT, PolicyLifecycleState.VALIDATING)
    assert not is_allowed_transition(PolicyLifecycleState.DRAFT, PolicyLifecycleState.ACTIVE)


def test_require_allowed_transition_passes_silently_when_allowed() -> None:
    require_allowed_transition(PolicyLifecycleState.APPROVED, PolicyLifecycleState.ACTIVE)


def test_require_allowed_transition_raises_when_disallowed() -> None:
    with pytest.raises(PolicyLifecycleTransitionError) as excinfo:
        require_allowed_transition(PolicyLifecycleState.DRAFT, PolicyLifecycleState.RETIRED)
    assert excinfo.value.current is PolicyLifecycleState.DRAFT
    assert excinfo.value.target is PolicyLifecycleState.RETIRED


def test_a_retired_policy_cannot_transition_anywhere() -> None:
    for target in PolicyLifecycleState:
        if target is PolicyLifecycleState.RETIRED:
            continue
        with pytest.raises(PolicyLifecycleTransitionError):
            require_allowed_transition(PolicyLifecycleState.RETIRED, target)


def test_authoring_separation_passes_for_two_distinct_identities() -> None:
    require_authoring_separation(author_id="subject.author", approver_id="subject.approver")


def test_authoring_separation_raises_for_the_same_identity() -> None:
    with pytest.raises(PolicyAuthoringSeparationError) as excinfo:
        require_authoring_separation(author_id="subject.same", approver_id="subject.same")
    assert excinfo.value.identity_id == "subject.same"
