from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.runbook_engine.domain.plan_generation import (
    DerivedPlan,
    PlanOutputKind,
    requires_policy_decision_binding,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def plan(**overrides: object) -> DerivedPlan:
    defaults: dict[str, object] = {
        "plan_id": "runbook-plan.example",
        "kind": PlanOutputKind.HUMAN_CHECKLIST,
        "source_runbook_id": "runbook.example",
        "source_version_id": "runbook-version.example",
        "target_id": "target.example",
        "bound_parameters": (("controller_id", "controller-b"),),
        "bound_evidence_references": ("evidence.example",),
        "bound_policy_decision_id": None,
        "bound_impact_analysis_reference": None,
        "created_at": NOW,
        "created_by": "subject.requester",
    }
    defaults.update(overrides)
    return DerivedPlan(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (PlanOutputKind.HUMAN_CHECKLIST, False),
        (PlanOutputKind.INCIDENT_DIAGNOSTIC_PLAN, False),
        (PlanOutputKind.TARGET_SPECIFIC_RECOMMENDATION_PLAN, False),
        (PlanOutputKind.WORKFLOW_DRAFT, True),
        (PlanOutputKind.APPROVAL_PACKET_INPUT, True),
    ],
)
def test_requires_policy_decision_binding(kind: PlanOutputKind, expected: bool) -> None:
    assert requires_policy_decision_binding(kind) is expected


def test_a_well_formed_plan_constructs_cleanly() -> None:
    example = plan()
    assert example.kind is PlanOutputKind.HUMAN_CHECKLIST


def test_workflow_draft_requires_a_bound_policy_decision() -> None:
    with pytest.raises(ValueError, match="requires a bound policy decision"):
        plan(kind=PlanOutputKind.WORKFLOW_DRAFT, bound_policy_decision_id=None)


def test_approval_packet_input_requires_a_bound_policy_decision() -> None:
    with pytest.raises(ValueError, match="requires a bound policy decision"):
        plan(kind=PlanOutputKind.APPROVAL_PACKET_INPUT, bound_policy_decision_id=None)


def test_workflow_draft_constructs_with_a_bound_policy_decision() -> None:
    example = plan(
        kind=PlanOutputKind.WORKFLOW_DRAFT, bound_policy_decision_id="policy-decision.example"
    )
    assert example.bound_policy_decision_id == "policy-decision.example"


def test_human_checklist_does_not_require_a_bound_policy_decision() -> None:
    example = plan(kind=PlanOutputKind.HUMAN_CHECKLIST, bound_policy_decision_id=None)
    assert example.bound_policy_decision_id is None


def test_rejects_blank_created_by() -> None:
    with pytest.raises(ValueError, match="who created it"):
        plan(created_by="   ")


def test_rejects_naive_created_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        plan(created_at=NOW.replace(tzinfo=None))
