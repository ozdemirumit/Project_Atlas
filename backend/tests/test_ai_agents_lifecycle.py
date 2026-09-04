from __future__ import annotations

import pytest

from atlas.modules.ai_agents.domain.definition import AgentLifecycleState
from atlas.modules.ai_agents.domain.lifecycle import (
    ActivationRequirements,
    AgentEvaluationCriterion,
    AgentEvaluationResult,
    EvaluationCaseKind,
    is_valid_transition,
    require_activation_requirements,
)


def evaluation(**overrides: object) -> AgentEvaluationResult:
    defaults: dict[str, object] = {
        "agent_id": "agent.health-analysis",
        "agent_version": 1,
        "criterion_results": tuple((criterion, True) for criterion in AgentEvaluationCriterion),
        "case_kind_coverage": (EvaluationCaseKind.NORMAL, EvaluationCaseKind.ADVERSARIAL),
    }
    defaults.update(overrides)
    return AgentEvaluationResult(**defaults)  # type: ignore[arg-type]


def test_evaluation_result_requires_every_criterion() -> None:
    with pytest.raises(ValueError, match="every evaluation criterion"):
        evaluation(
            criterion_results=(
                (AgentEvaluationCriterion.TASK_COMPLETION_AND_STRUCTURED_OUTPUT_VALIDITY, True),
            )
        )


def test_evaluation_result_rejects_duplicate_case_kind() -> None:
    with pytest.raises(ValueError, match="must not repeat a case kind"):
        evaluation(case_kind_coverage=(EvaluationCaseKind.NORMAL, EvaluationCaseKind.NORMAL))


def test_evaluation_result_passed_true_when_all_criteria_pass() -> None:
    assert evaluation().passed is True


def test_evaluation_result_passed_false_when_one_criterion_fails() -> None:
    results = tuple(
        (criterion, criterion != AgentEvaluationCriterion.CROSS_ORGANIZATION_ISOLATION)
        for criterion in AgentEvaluationCriterion
    )
    assert evaluation(criterion_results=results).passed is False


@pytest.mark.parametrize(
    ("from_state", "to_state", "expected"),
    [
        (AgentLifecycleState.DRAFT, AgentLifecycleState.EVALUATING, True),
        (AgentLifecycleState.EVALUATING, AgentLifecycleState.DRAFT, True),
        (AgentLifecycleState.EVALUATING, AgentLifecycleState.APPROVED, True),
        (AgentLifecycleState.APPROVED, AgentLifecycleState.ACTIVE, True),
        (AgentLifecycleState.ACTIVE, AgentLifecycleState.SUSPENDED, True),
        (AgentLifecycleState.SUSPENDED, AgentLifecycleState.ACTIVE, True),
        (AgentLifecycleState.ACTIVE, AgentLifecycleState.SUPERSEDED, True),
        (AgentLifecycleState.SUPERSEDED, AgentLifecycleState.RETIRED, True),
        (AgentLifecycleState.SUSPENDED, AgentLifecycleState.RETIRED, True),
        (AgentLifecycleState.RETIRED, AgentLifecycleState.ACTIVE, False),
        (AgentLifecycleState.DRAFT, AgentLifecycleState.ACTIVE, False),
        (AgentLifecycleState.APPROVED, AgentLifecycleState.RETIRED, False),
    ],
)
def test_is_valid_transition(
    from_state: AgentLifecycleState, to_state: AgentLifecycleState, expected: bool
) -> None:
    assert is_valid_transition(from_state=from_state, to_state=to_state) is expected


def test_no_lifecycle_state_can_self_transition() -> None:
    for state in AgentLifecycleState:
        assert is_valid_transition(from_state=state, to_state=state) is False


def requirements(**overrides: object) -> ActivationRequirements:
    defaults: dict[str, object] = {
        "has_owner": True,
        "has_compatible_model_and_tools": True,
        "evaluation": evaluation(),
        "has_review": True,
        "has_rollback_path": True,
    }
    defaults.update(overrides)
    return ActivationRequirements(**defaults)  # type: ignore[arg-type]


def test_require_activation_requirements_passes_when_satisfied() -> None:
    require_activation_requirements(requirements())


def test_require_activation_requirements_raises_without_rollback_path() -> None:
    with pytest.raises(ValueError, match="rollback path"):
        require_activation_requirements(requirements(has_rollback_path=False))


def test_require_activation_requirements_raises_when_evaluation_failed() -> None:
    failing = evaluation(
        criterion_results=tuple((criterion, False) for criterion in AgentEvaluationCriterion)
    )
    with pytest.raises(ValueError, match="activation requires"):
        require_activation_requirements(requirements(evaluation=failing))
