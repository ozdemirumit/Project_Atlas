from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.runbook_engine.domain.branching import (
    BranchCondition,
    BranchDestination,
    BranchOutcome,
    BranchPath,
    RunbookBranch,
    RunbookLoop,
    branch_broadens_capability_class,
    requires_policy_reevaluation,
)
from atlas.modules.runbook_engine.domain.structure import RunbookStep, RunbookStepActor


def condition(**overrides: object) -> BranchCondition:
    defaults: dict[str, object] = {
        "observed_field": "controller_b.health_state",
        "comparison": "equals",
        "expected_value": "healthy",
    }
    defaults.update(overrides)
    return BranchCondition(**defaults)  # type: ignore[arg-type]


def _all_paths(
    overrides_by_outcome: dict[BranchOutcome, BranchDestination] | None = None,
) -> tuple[BranchPath, ...]:
    destinations = {
        BranchOutcome.TRUE: BranchDestination.NEXT_STEP,
        BranchOutcome.FALSE: BranchDestination.SAFE_STOP,
        BranchOutcome.UNKNOWN: BranchDestination.ROUTE_TO_REVIEW,
        BranchOutcome.TIMEOUT: BranchDestination.SAFE_STOP,
        BranchOutcome.ERROR: BranchDestination.SAFE_STOP,
    }
    if overrides_by_outcome:
        destinations.update(overrides_by_outcome)
    paths = []
    for outcome, destination in destinations.items():
        next_step_id = "runbook-step.next" if destination is BranchDestination.NEXT_STEP else None
        paths.append(
            BranchPath(outcome=outcome, destination=destination, next_step_id=next_step_id)
        )
    return tuple(paths)


def branch(**overrides: object) -> RunbookBranch:
    defaults: dict[str, object] = {
        "branch_id": "runbook-branch.example",
        "step_id": "runbook-step.example",
        "condition": condition(),
        "paths": _all_paths(),
    }
    defaults.update(overrides)
    return RunbookBranch(**defaults)  # type: ignore[arg-type]


def test_branch_condition_requires_all_fields() -> None:
    with pytest.raises(ValueError, match="observed field"):
        condition(observed_field="   ")


def test_branch_path_next_step_requires_next_step_id() -> None:
    with pytest.raises(ValueError, match="requires next_step_id"):
        BranchPath(
            outcome=BranchOutcome.TRUE, destination=BranchDestination.NEXT_STEP, next_step_id=None
        )


def test_branch_path_non_next_step_cannot_carry_next_step_id() -> None:
    with pytest.raises(ValueError, match="only meaningful when destination is NEXT_STEP"):
        BranchPath(
            outcome=BranchOutcome.FALSE,
            destination=BranchDestination.SAFE_STOP,
            next_step_id="runbook-step.next",
        )


def test_a_well_formed_branch_constructs_cleanly() -> None:
    example = branch()
    assert len(example.paths) == 5


def test_branch_requires_a_path_for_every_outcome() -> None:
    incomplete = tuple(p for p in _all_paths() if p.outcome is not BranchOutcome.ERROR)
    with pytest.raises(ValueError, match="missing"):
        branch(paths=incomplete)


def test_branch_rejects_duplicate_paths_for_the_same_outcome() -> None:
    duplicated = (
        *_all_paths(),
        BranchPath(
            outcome=BranchOutcome.TRUE, destination=BranchDestination.SAFE_STOP, next_step_id=None
        ),
    )
    with pytest.raises(ValueError, match="more than one path per outcome"):
        branch(paths=duplicated)


def test_unknown_outcome_cannot_route_to_next_step() -> None:
    with pytest.raises(ValueError, match="never silently to the next step"):
        branch(paths=_all_paths({BranchOutcome.UNKNOWN: BranchDestination.NEXT_STEP}))


def test_runbook_loop_requires_positive_maximum_iterations() -> None:
    with pytest.raises(ValueError, match="maximum iteration"):
        RunbookLoop(
            loop_id="runbook-loop.example",
            maximum_iterations=0,
            deadline_seconds=60,
            exit_conditions=("x",),
        )


def test_runbook_loop_requires_positive_deadline() -> None:
    with pytest.raises(ValueError, match="positive deadline"):
        RunbookLoop(
            loop_id="runbook-loop.example",
            maximum_iterations=3,
            deadline_seconds=0,
            exit_conditions=("x",),
        )


def test_runbook_loop_requires_at_least_one_exit_condition() -> None:
    with pytest.raises(ValueError, match="exit condition"):
        RunbookLoop(
            loop_id="runbook-loop.example",
            maximum_iterations=3,
            deadline_seconds=60,
            exit_conditions=(),
        )


def test_runbook_loop_constructs_cleanly() -> None:
    example = RunbookLoop(
        loop_id="runbook-loop.example",
        maximum_iterations=5,
        deadline_seconds=600,
        exit_conditions=("Controller B reports healthy.",),
    )
    assert example.maximum_iterations == 5


def step(**overrides: object) -> RunbookStep:
    defaults: dict[str, object] = {
        "step_id": "runbook-step.example",
        "version": 1,
        "purpose": "Restart controller B.",
        "expected_state_transition": "Controller B moves from degraded to healthy.",
        "actor": RunbookStepActor.GOVERNED_CONNECTOR,
        "target_selector": "target.example",
        "capability_id": "capability.storage.controller.restart",
        "capability_version": "1",
        "capability_class": CapabilityClass.C1_READ_ONLY,
        "required_role": None,
        "requires_approval": False,
        "requires_change_window": False,
        "instructions": "Issue a graceful restart to controller B and monitor for recovery.",
        "expected_duration_minimum_minutes": 1,
        "expected_duration_maximum_minutes": 5,
        "expected_result": "Controller B reports healthy status.",
        "timeout_seconds": 600,
        "retryable": False,
        "idempotent": False,
        "cancellable": True,
        "stop_conditions": (),
        "precondition_ids": (),
        "rollback_or_recovery_reference": None,
        "evidence_output_references": (),
    }
    defaults.update(overrides)
    return RunbookStep(**defaults)  # type: ignore[arg-type]


def test_branch_broadens_capability_class_when_destination_ranks_higher() -> None:
    from_step = step(capability_class=CapabilityClass.C1_READ_ONLY)
    to_step = step(capability_class=CapabilityClass.C4_SERVICE_IMPACTING)
    assert branch_broadens_capability_class(from_step=from_step, to_step=to_step) is True


def test_branch_does_not_broaden_when_destination_ranks_lower_or_equal() -> None:
    from_step = step(capability_class=CapabilityClass.C3_CONTROLLED_CHANGE)
    to_step = step(capability_class=CapabilityClass.C1_READ_ONLY)
    assert branch_broadens_capability_class(from_step=from_step, to_step=to_step) is False
    same_class_step = step(capability_class=CapabilityClass.C3_CONTROLLED_CHANGE)
    assert branch_broadens_capability_class(from_step=from_step, to_step=same_class_step) is False


def test_requires_policy_reevaluation_for_a_non_foundation_capability_class() -> None:
    assert (
        requires_policy_reevaluation(
            to_step=step(capability_class=CapabilityClass.C3_CONTROLLED_CHANGE)
        )
        is True
    )


def test_requires_policy_reevaluation_for_a_step_that_requires_approval() -> None:
    example = step(capability_class=CapabilityClass.C0_INFORMATIONAL, requires_approval=True)
    assert requires_policy_reevaluation(to_step=example) is True


def test_does_not_require_policy_reevaluation_for_a_foundation_step_without_approval() -> None:
    example = step(capability_class=CapabilityClass.C1_READ_ONLY, requires_approval=False)
    assert requires_policy_reevaluation(to_step=example) is False
