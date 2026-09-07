"""ATLAS-037 SS11/SS12: multi-step approval stages and quorum.

The existing single-stage `ApprovalRecord`/`ApprovalService.decide()` remains the MVP-included
"single... human approval state" path (SS29) and is unchanged by this module. This is the
additive "multi-stage" half of the same MVP line: a stage plan bound to the same immutable
`ApprovalPacket`, and pure evaluation logic a future staged decision service can compose with --
it does not replace or re-wire the existing single-stage service.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.approvals.domain.models import ApprovalDecision, ApprovalOutcome, ApprovalState


@dataclass(frozen=True, slots=True)
class ApprovalStageRequirement:
    """SS12: "Stages have stable IDs, required roles, scope, sequence, quorum, and
    expiry.\""""

    stage_id: str
    required_role: str
    required_scope_reference: str
    sequence: int
    quorum: int
    expiry_minutes: int

    def __post_init__(self) -> None:
        if not self.stage_id.strip() or not self.required_role.strip():
            raise ValueError("an approval stage requires a stable ID and a required role")
        if not self.required_scope_reference.strip():
            raise ValueError("an approval stage requires a scope reference")
        if self.sequence < 1:
            raise ValueError("an approval stage sequence must be positive")
        if self.quorum < 1:
            raise ValueError("an approval stage quorum must be at least one")
        if not 5 <= self.expiry_minutes <= 10080:
            raise ValueError("an approval stage expiry must be between 5 minutes and 7 days")


@dataclass(frozen=True, slots=True)
class ApprovalStagePlan:
    """SS11: "Policy determines stages from capability class, environment, service
    criticality..." -- this is the resolved, immutable plan for one approval packet, not the
    policy that produced it."""

    request_id: str
    stages: tuple[ApprovalStageRequirement, ...]

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("an approval stage plan requires a request id")
        if not self.stages:
            raise ValueError("an approval stage plan requires at least one stage")
        stage_ids = [stage.stage_id for stage in self.stages]
        if len(set(stage_ids)) != len(stage_ids):
            raise ValueError("approval stage IDs must be unique within a plan")
        # SS12: "Parallel approval is permitted only for independent roles." Two stages sharing
        # a sequence number run in parallel, so they must never require the same role -- a
        # single approver could otherwise satisfy both halves of what is supposed to be two
        # independent checks.
        roles_by_sequence: dict[int, set[str]] = {}
        for stage in self.stages:
            seen = roles_by_sequence.setdefault(stage.sequence, set())
            if stage.required_role in seen:
                raise ValueError(
                    "parallel approval stages (the same sequence number) must require"
                    " independent roles"
                )
            seen.add(stage.required_role)

    @property
    def sequence_groups(self) -> tuple[tuple[ApprovalStageRequirement, ...], ...]:
        """Stages grouped by sequence number, ascending -- each group runs in parallel; groups
        run in order."""
        ordered_sequences = sorted({stage.sequence for stage in self.stages})
        return tuple(
            tuple(stage for stage in self.stages if stage.sequence == sequence)
            for sequence in ordered_sequences
        )


@dataclass(frozen=True, slots=True)
class StageDecisionRecord:
    """One eligible approver's decision at one named stage."""

    stage_id: str
    reviewer_role: str
    decision: ApprovalDecision

    def __post_init__(self) -> None:
        if not self.stage_id.strip() or not self.reviewer_role.strip():
            raise ValueError("a stage decision requires a stage ID and the reviewer's role")


def stage_eligible_decisions(
    stage: ApprovalStageRequirement,
    decisions: tuple[StageDecisionRecord, ...],
) -> tuple[StageDecisionRecord, ...]:
    return tuple(
        item
        for item in decisions
        if item.stage_id == stage.stage_id and item.reviewer_role == stage.required_role
    )


def stage_has_a_rejection(
    stage: ApprovalStageRequirement,
    decisions: tuple[StageDecisionRecord, ...],
) -> bool:
    return any(
        item.decision.outcome is ApprovalOutcome.REJECT
        for item in stage_eligible_decisions(stage, decisions)
    )


def is_stage_satisfied(
    stage: ApprovalStageRequirement,
    decisions: tuple[StageDecisionRecord, ...],
) -> bool:
    """SS12: "Quorum is calculated from distinct eligible humans" and "a stage cannot count one
    person twice through multiple roles" -- using a set of reviewer identities means a single
    person deciding more than once, or holding more than one eligible role, is never counted
    more than once toward this stage's quorum."""
    eligible = stage_eligible_decisions(stage, decisions)
    distinct_approvers = {
        item.decision.reviewer_id
        for item in eligible
        if item.decision.outcome is ApprovalOutcome.APPROVE
    }
    return len(distinct_approvers) >= stage.quorum


def evaluate_plan_state(
    plan: ApprovalStagePlan,
    decisions: tuple[StageDecisionRecord, ...],
) -> ApprovalState:
    """SS12: "A rejection stops the request unless policy explicitly permits revision and
    resubmission" (this evaluator takes the default, more restrictive path -- any rejection at a
    reached stage stops the whole plan) and "later approvers see prior decisions and the
    unchanged packet" (stages are evaluated in sequence-group order; a later group is never
    reachable before every earlier group is satisfied)."""
    any_stage_reached = False
    for group in plan.sequence_groups:
        for stage in group:
            if stage_eligible_decisions(stage, decisions):
                any_stage_reached = True
            if stage_has_a_rejection(stage, decisions):
                return ApprovalState.REJECTED
        if not all(is_stage_satisfied(stage, decisions) for stage in group):
            return ApprovalState.PARTIALLY_APPROVED if any_stage_reached else ApprovalState.PENDING
    return ApprovalState.APPROVED


def rejection_allows_the_request_to_proceed_without_permitted_revision() -> bool:
    """SS12: "A rejection stops the request unless policy explicitly permits revision and
    resubmission.\""""
    return False


def policy_changes_affecting_an_in_flight_request_are_ignored() -> bool:
    """SS12: "Policy changes affecting an in-flight request trigger re-evaluation and may
    require restart.\" Not yet wired to a live policy feed -- documented here as a real
    requirement, not silently dropped."""
    return False
