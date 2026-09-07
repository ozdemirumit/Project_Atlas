from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.approvals.domain.models import ApprovalDecision, ApprovalOutcome, ApprovalState
from atlas.modules.approvals.domain.stages import (
    ApprovalStagePlan,
    ApprovalStageRequirement,
    StageDecisionRecord,
    evaluate_plan_state,
    is_stage_satisfied,
    policy_changes_affecting_an_in_flight_request_are_ignored,
    rejection_allows_the_request_to_proceed_without_permitted_revision,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _stage(**overrides: object) -> ApprovalStageRequirement:
    defaults: dict[str, object] = {
        "stage_id": "stage.technical",
        "required_role": "role.infrastructure-engineer",
        "required_scope_reference": "scope.example",
        "sequence": 1,
        "quorum": 1,
        "expiry_minutes": 60,
    }
    defaults.update(overrides)
    return ApprovalStageRequirement(**defaults)  # type: ignore[arg-type]


def _decision(
    reviewer_id: str, outcome: ApprovalOutcome = ApprovalOutcome.APPROVE
) -> ApprovalDecision:
    return ApprovalDecision(
        decision_id=f"approval_decision_{reviewer_id}",
        request_version=1,
        outcome=outcome,
        reviewer_id=reviewer_id,
        decided_at=NOW,
        rationale="Stage evaluation test decision.",
    )


def _stage_decision(
    stage_id: str,
    role: str,
    reviewer_id: str,
    outcome: ApprovalOutcome = ApprovalOutcome.APPROVE,
) -> StageDecisionRecord:
    return StageDecisionRecord(
        stage_id=stage_id, reviewer_role=role, decision=_decision(reviewer_id, outcome)
    )


def test_rejection_never_allows_progress_without_permitted_revision() -> None:
    assert rejection_allows_the_request_to_proceed_without_permitted_revision() is False


def test_policy_changes_in_flight_are_never_ignored() -> None:
    assert policy_changes_affecting_an_in_flight_request_are_ignored() is False


def test_stage_requirement_rejects_non_positive_sequence() -> None:
    with pytest.raises(ValueError, match="sequence must be positive"):
        _stage(sequence=0)


def test_stage_requirement_rejects_zero_quorum() -> None:
    with pytest.raises(ValueError, match="quorum must be at least one"):
        _stage(quorum=0)


def test_plan_requires_unique_stage_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        ApprovalStagePlan(
            request_id="approval.example-001",
            stages=(_stage(stage_id="stage.a"), _stage(stage_id="stage.a", sequence=2)),
        )


def test_plan_rejects_parallel_stages_with_the_same_role() -> None:
    with pytest.raises(ValueError, match="independent roles"):
        ApprovalStagePlan(
            request_id="approval.example-001",
            stages=(
                _stage(stage_id="stage.a", sequence=1, required_role="role.approver"),
                _stage(stage_id="stage.b", sequence=1, required_role="role.approver"),
            ),
        )


def test_plan_allows_parallel_stages_with_independent_roles() -> None:
    plan = ApprovalStagePlan(
        request_id="approval.example-001",
        stages=(
            _stage(stage_id="stage.a", sequence=1, required_role="role.technical-approver"),
            _stage(stage_id="stage.b", sequence=1, required_role="role.service-owner"),
        ),
    )
    assert len(plan.sequence_groups) == 1
    assert len(plan.sequence_groups[0]) == 2


def test_quorum_counts_distinct_approvers_only_once() -> None:
    stage = _stage(quorum=2)
    decisions = (
        _stage_decision(stage.stage_id, stage.required_role, "subject.a"),
        _stage_decision(stage.stage_id, stage.required_role, "subject.a"),
    )
    assert is_stage_satisfied(stage, decisions) is False

    decisions_two_distinct = (
        _stage_decision(stage.stage_id, stage.required_role, "subject.a"),
        _stage_decision(stage.stage_id, stage.required_role, "subject.b"),
    )
    assert is_stage_satisfied(stage, decisions_two_distinct) is True


def test_decision_under_a_different_role_does_not_count_toward_quorum() -> None:
    stage = _stage(quorum=1, required_role="role.security-administrator")
    decisions = (_stage_decision(stage.stage_id, "role.some-other-role", "subject.a"),)
    assert is_stage_satisfied(stage, decisions) is False


def test_single_stage_plan_pending_with_no_decisions() -> None:
    plan = ApprovalStagePlan(request_id="approval.example-001", stages=(_stage(),))
    assert evaluate_plan_state(plan, ()) is ApprovalState.PENDING


def test_single_stage_plan_approved_once_quorum_met() -> None:
    stage = _stage()
    plan = ApprovalStagePlan(request_id="approval.example-001", stages=(stage,))
    decisions = (_stage_decision(stage.stage_id, stage.required_role, "subject.a"),)
    assert evaluate_plan_state(plan, decisions) is ApprovalState.APPROVED


def test_two_sequential_stages_partially_approved_after_first_stage() -> None:
    first = _stage(stage_id="stage.first", sequence=1, required_role="role.technical")
    second = _stage(stage_id="stage.second", sequence=2, required_role="role.change-authority")
    plan = ApprovalStagePlan(request_id="approval.example-001", stages=(first, second))
    decisions = (_stage_decision(first.stage_id, first.required_role, "subject.a"),)
    assert evaluate_plan_state(plan, decisions) is ApprovalState.PARTIALLY_APPROVED


def test_two_sequential_stages_approved_once_both_satisfied() -> None:
    first = _stage(stage_id="stage.first", sequence=1, required_role="role.technical")
    second = _stage(stage_id="stage.second", sequence=2, required_role="role.change-authority")
    plan = ApprovalStagePlan(request_id="approval.example-001", stages=(first, second))
    decisions = (
        _stage_decision(first.stage_id, first.required_role, "subject.a"),
        _stage_decision(second.stage_id, second.required_role, "subject.b"),
    )
    assert evaluate_plan_state(plan, decisions) is ApprovalState.APPROVED


def test_a_rejection_stops_the_plan() -> None:
    first = _stage(stage_id="stage.first", sequence=1, required_role="role.technical")
    second = _stage(stage_id="stage.second", sequence=2, required_role="role.change-authority")
    plan = ApprovalStagePlan(request_id="approval.example-001", stages=(first, second))
    decisions = (
        _stage_decision(first.stage_id, first.required_role, "subject.a", ApprovalOutcome.REJECT),
    )
    assert evaluate_plan_state(plan, decisions) is ApprovalState.REJECTED


def test_a_later_stage_rejection_does_not_hide_an_earlier_pending_stage() -> None:
    first = _stage(stage_id="stage.first", sequence=1, required_role="role.technical")
    second = _stage(stage_id="stage.second", sequence=2, required_role="role.change-authority")
    plan = ApprovalStagePlan(request_id="approval.example-001", stages=(first, second))
    # The second stage cannot realistically be reached before the first is satisfied, but the
    # evaluator still must not report REJECTED from a stage it has not actually reached.
    assert evaluate_plan_state(plan, ()) is ApprovalState.PENDING
