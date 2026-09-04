from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.runbook_engine.domain.applicability import (
    ApplicabilityFactor,
    ApplicabilityFactorKind,
    ApplicabilityFactorResult,
    ApplicabilityMatch,
)
from atlas.modules.runbook_engine.domain.branching import (
    BranchCondition,
    BranchDestination,
    BranchOutcome,
    BranchPath,
    RunbookBranch,
)
from atlas.modules.runbook_engine.domain.handoff import (
    OperatorRecordedResult,
    OperatorRecordKind,
    RunbookHandoffView,
    is_available_to_autonomous_ai,
)
from atlas.modules.runbook_engine.domain.preconditions import (
    PreconditionCategory,
    PreconditionFailureBehavior,
    RunbookPrecondition,
)
from atlas.modules.runbook_engine.domain.risk_impact import (
    DurationRange,
    RunbookRiskImpactDuration,
)
from atlas.modules.runbook_engine.domain.rollback_recovery import (
    RollbackRecoveryKind,
    RunbookRollbackOrRecovery,
)
from atlas.modules.runbook_engine.domain.structure import RunbookStep, RunbookStepActor

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("capability_class", "expected"),
    [
        (CapabilityClass.C0_INFORMATIONAL, True),
        (CapabilityClass.C1_READ_ONLY, True),
        (CapabilityClass.C2_DIAGNOSTIC, True),
        (CapabilityClass.C3_CONTROLLED_CHANGE, False),
        (CapabilityClass.C4_SERVICE_IMPACTING, False),
        (CapabilityClass.C5_DESTRUCTIVE, False),
    ],
)
def test_is_available_to_autonomous_ai(capability_class: CapabilityClass, expected: bool) -> None:
    assert is_available_to_autonomous_ai(capability_class) is expected


def operator_record(**overrides: object) -> OperatorRecordedResult:
    defaults: dict[str, object] = {
        "record_id": "operator-record.example",
        "step_id": "runbook-step.example",
        "kind": OperatorRecordKind.ACTUAL_RESULT,
        "recorded_by": "subject.operator",
        "recorded_at": NOW,
        "actual_result": "Controller B reported healthy after restart.",
        "deviation_note": None,
    }
    defaults.update(overrides)
    return OperatorRecordedResult(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_operator_record_constructs_cleanly() -> None:
    example = operator_record()
    assert example.kind is OperatorRecordKind.ACTUAL_RESULT


def test_deviation_record_requires_a_deviation_note() -> None:
    with pytest.raises(ValueError, match="requires a deviation_note"):
        operator_record(kind=OperatorRecordKind.DEVIATION, deviation_note=None)


def test_deviation_record_constructs_with_a_note() -> None:
    example = operator_record(
        kind=OperatorRecordKind.DEVIATION,
        deviation_note="Used controller A's alternate restart sequence instead.",
    )
    assert example.deviation_note is not None


def test_actual_result_record_cannot_carry_a_deviation_note() -> None:
    with pytest.raises(ValueError, match="only meaningful for a DEVIATION"):
        operator_record(
            kind=OperatorRecordKind.ACTUAL_RESULT, deviation_note="Not applicable here."
        )


def test_operator_record_requires_who_recorded_it() -> None:
    with pytest.raises(ValueError, match="who recorded it"):
        operator_record(recorded_by="   ")


def applicability() -> ApplicabilityMatch:
    return ApplicabilityMatch(
        runbook_id="runbook.example",
        version_id="runbook-version.example",
        target_id="target.example",
        factors=(
            ApplicabilityFactor(
                kind=ApplicabilityFactorKind.VENDOR_AND_VERSION_COMPATIBILITY,
                result=ApplicabilityFactorResult.EXACT,
                explanation="The target's firmware matches the runbook's tested version.",
            ),
        ),
    )


def precondition() -> RunbookPrecondition:
    return RunbookPrecondition(
        precondition_id="runbook-precondition.example",
        category=PreconditionCategory.HEALTH_AND_PROTECTION_STATE,
        description="The redundant storage path reports healthy.",
        verification_method="Query the storage array's path health API.",
        freshness_limit_seconds=300,
        failure_behavior=PreconditionFailureBehavior.BLOCKS,
        alternative_procedure_reference=None,
    )


def step() -> RunbookStep:
    return RunbookStep(
        step_id="runbook-step.example",
        version=1,
        purpose="Restart controller B.",
        expected_state_transition="Controller B moves from degraded to healthy.",
        actor=RunbookStepActor.HUMAN,
        target_selector="target.example",
        capability_id=None,
        capability_version=None,
        capability_class=CapabilityClass.C1_READ_ONLY,
        required_role=None,
        requires_approval=False,
        requires_change_window=False,
        instructions="Issue a graceful restart to controller B and monitor for recovery.",
        expected_duration_minimum_minutes=1,
        expected_duration_maximum_minutes=5,
        expected_result="Controller B reports healthy status.",
        timeout_seconds=600,
        retryable=False,
        idempotent=False,
        cancellable=True,
        stop_conditions=(),
        precondition_ids=(),
        rollback_or_recovery_reference=None,
        evidence_output_references=(),
    )


def branch() -> RunbookBranch:
    paths = (
        BranchPath(
            outcome=BranchOutcome.TRUE,
            destination=BranchDestination.NEXT_STEP,
            next_step_id="runbook-step.next",
        ),
        BranchPath(
            outcome=BranchOutcome.FALSE, destination=BranchDestination.SAFE_STOP, next_step_id=None
        ),
        BranchPath(
            outcome=BranchOutcome.UNKNOWN,
            destination=BranchDestination.ROUTE_TO_REVIEW,
            next_step_id=None,
        ),
        BranchPath(
            outcome=BranchOutcome.TIMEOUT,
            destination=BranchDestination.SAFE_STOP,
            next_step_id=None,
        ),
        BranchPath(
            outcome=BranchOutcome.ERROR, destination=BranchDestination.SAFE_STOP, next_step_id=None
        ),
    )
    return RunbookBranch(
        branch_id="runbook-branch.example",
        step_id="runbook-step.example",
        condition=BranchCondition(
            observed_field="controller_b.health_state",
            comparison="equals",
            expected_value="healthy",
        ),
        paths=paths,
    )


def risk_impact() -> RunbookRiskImpactDuration:
    duration = DurationRange(minimum_minutes=1, maximum_minutes=5)
    return RunbookRiskImpactDuration(
        runbook_id="runbook.example",
        version_id="runbook-version.example",
        direct_affected_systems=("controller-b",),
        transitive_affected_systems=(),
        affected_services=("service.file-shares",),
        interruption_expected_mode="none",
        interruption_range=duration,
        preparation_duration=duration,
        execution_duration=duration,
        stabilization_duration=duration,
        validation_duration=duration,
        rollback_duration=duration,
        recovery_duration=duration,
        redundancy_effect="Momentary loss of path redundancy during restart.",
        capacity_effect="None.",
        data_effect="None.",
        security_effect="None.",
        compliance_effect="None.",
        worst_credible_outcome="Failover to controller A with a brief path interruption.",
        residual_risk="A concurrent controller A fault would extend the outage.",
        point_of_no_return_step_id=None,
        irreversible_step_ids=(),
        requires_target_specific_impact_analysis=True,
    )


def rollback_recovery() -> RunbookRollbackOrRecovery:
    return RunbookRollbackOrRecovery(
        reference_id="runbook-rollback.example",
        kind=RollbackRecoveryKind.ROLLBACK,
        forward_step_id="runbook-step.example",
        checkpoint_id=None,
        entry_criteria="The forward step failed before completion.",
        responsible_role="role.storage-operator",
        required_resources=(),
        estimated_duration=DurationRange(minimum_minutes=1, maximum_minutes=5),
        service_effect="Momentary path interruption during rollback.",
        has_been_tested=True,
        is_irreversible=False,
        partial_execution_recovery_reference="runbook-recovery.partial-example",
        unknown_outcome_recovery_reference="runbook-recovery.unknown-example",
    )


def handoff_view(**overrides: object) -> RunbookHandoffView:
    defaults: dict[str, object] = {
        "runbook_id": "runbook.example",
        "version_id": "runbook-version.example",
        "plan_id": "runbook-plan.example",
        "target_id": "target.example",
        "environment_id": "environment.production",
        "applicability": applicability(),
        "roles_and_responsibilities": (("role.storage-operator", "Executes the restart."),),
        "preconditions": (precondition(),),
        "steps": (step(),),
        "branches": (branch(),),
        "risk_impact": risk_impact(),
        "rollback_and_recovery": (rollback_recovery(),),
        "required_approval_reference": "approval-request.example",
        "itsm_context_reference": "incident.example",
        "evidence_capture_checklist": ("Capture controller B's post-restart health output.",),
        "service_validation_checklist": ("Confirm file-share service is reachable.",),
    }
    defaults.update(overrides)
    return RunbookHandoffView(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_handoff_view_constructs_cleanly() -> None:
    example = handoff_view()
    assert len(example.steps) == 1


def test_handoff_view_requires_at_least_one_step() -> None:
    with pytest.raises(ValueError, match="at least one ordered step"):
        handoff_view(steps=())


def test_handoff_view_carries_the_aggregated_risk_impact() -> None:
    example = handoff_view()
    assert example.risk_impact.direct_affected_systems == ("controller-b",)


def test_handoff_view_carries_rollback_and_recovery() -> None:
    example = handoff_view()
    assert example.rollback_and_recovery[0].kind is RollbackRecoveryKind.ROLLBACK
