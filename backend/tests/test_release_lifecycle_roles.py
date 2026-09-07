from __future__ import annotations

import pytest

from atlas.modules.release.domain.lifecycle_roles import (
    ReleaseLifecycleState,
    ReleaseRole,
    RoleAssignment,
    is_valid_transition,
    separation_of_duties_applies_to_high_risk_exceptions_and_production_approval,
)


def test_release_lifecycle_state_has_fourteen_members() -> None:
    assert len(ReleaseLifecycleState) == 14


@pytest.mark.parametrize(
    ("from_state", "to_state", "expected"),
    [
        (ReleaseLifecycleState.PLANNING, ReleaseLifecycleState.DEVELOPING, True),
        (ReleaseLifecycleState.DEVELOPING, ReleaseLifecycleState.FEATURE_COMPLETE, True),
        (ReleaseLifecycleState.FEATURE_COMPLETE, ReleaseLifecycleState.CANDIDATE, True),
        (ReleaseLifecycleState.CANDIDATE, ReleaseLifecycleState.CANDIDATE, True),
        (ReleaseLifecycleState.CANDIDATE, ReleaseLifecycleState.APPROVED, True),
        (ReleaseLifecycleState.CANDIDATE, ReleaseLifecycleState.REJECTED, True),
        (ReleaseLifecycleState.APPROVED, ReleaseLifecycleState.PUBLISHED, True),
        (ReleaseLifecycleState.PUBLISHED, ReleaseLifecycleState.DEPLOYING, True),
        (ReleaseLifecycleState.DEPLOYING, ReleaseLifecycleState.SUPPORTED, True),
        (ReleaseLifecycleState.DEPLOYING, ReleaseLifecycleState.ROLLED_BACK, True),
        (ReleaseLifecycleState.ROLLED_BACK, ReleaseLifecycleState.CANDIDATE, True),
        (ReleaseLifecycleState.SUPPORTED, ReleaseLifecycleState.MAINTENANCE, True),
        (ReleaseLifecycleState.MAINTENANCE, ReleaseLifecycleState.DEPRECATED, True),
        (ReleaseLifecycleState.DEPRECATED, ReleaseLifecycleState.END_OF_SUPPORT, True),
        (ReleaseLifecycleState.END_OF_SUPPORT, ReleaseLifecycleState.RETIRED, True),
        (ReleaseLifecycleState.REJECTED, ReleaseLifecycleState.CANDIDATE, False),
        (ReleaseLifecycleState.RETIRED, ReleaseLifecycleState.SUPPORTED, False),
        (ReleaseLifecycleState.PLANNING, ReleaseLifecycleState.PUBLISHED, False),
    ],
)
def test_is_valid_transition(
    from_state: ReleaseLifecycleState, to_state: ReleaseLifecycleState, expected: bool
) -> None:
    assert is_valid_transition(from_state=from_state, to_state=to_state) is expected


def test_terminal_states_have_no_outgoing_transitions() -> None:
    for state in (ReleaseLifecycleState.REJECTED, ReleaseLifecycleState.RETIRED):
        assert all(
            not is_valid_transition(from_state=state, to_state=candidate)
            for candidate in ReleaseLifecycleState
        )


def test_release_role_has_ten_members() -> None:
    assert len(ReleaseRole) == 10


def test_role_assignment_requires_assigned_identity() -> None:
    with pytest.raises(ValueError, match="requires an assigned identity"):
        RoleAssignment(role=ReleaseRole.RELEASE_MANAGER, assigned_identity="")


def test_separation_of_duties_always_applies() -> None:
    assert separation_of_duties_applies_to_high_risk_exceptions_and_production_approval() is True
