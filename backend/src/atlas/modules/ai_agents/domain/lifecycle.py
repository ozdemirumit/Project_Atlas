"""ATLAS-040 SS24/SS25: evaluation framework and agent lifecycle.

`require_activation_requirements` mirrors `policy_engine.domain.lifecycle.
require_mandatory_tests_pass`'s gate pattern (SS18's mandatory-test activation gate) -- raising
rather than returning a bool, so a caller transitioning an agent definition into `ACTIVE` cannot
silently ignore an unmet SS25 requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.ai_agents.domain.definition import AgentLifecycleState
from atlas.modules.identity.domain.models import validate_stable_identifier


class AgentEvaluationCriterion(StrEnum):
    """SS24's eleven evaluation criteria."""

    TASK_COMPLETION_AND_STRUCTURED_OUTPUT_VALIDITY = (
        "task_completion_and_structured_output_validity"
    )
    FACTUAL_SUPPORT_AND_CITATION_PRECISION = "factual_support_and_citation_precision"
    DOMAIN_CORRECTNESS_AND_APPLICABLE_VERSION_HANDLING = (
        "domain_correctness_and_applicable_version_handling"
    )
    UNCERTAINTY_ALTERNATIVES_AND_CALIBRATION = "uncertainty_alternatives_and_calibration"
    TARGET_SCOPE_AND_TEMPORAL_CORRECTNESS = "target_scope_and_temporal_correctness"
    TOOL_SELECTION_AND_MINIMAL_CALL_BEHAVIOR = "tool_selection_and_minimal_call_behavior"
    SECURITY_PRIVACY_PROMPT_INJECTION_AND_REFUSAL_BEHAVIOR = (
        "security_privacy_prompt_injection_and_refusal_behavior"
    )
    RISK_IMPACT_INTERRUPTION_AND_RECOVERY_COMPLETENESS = (
        "risk_impact_interruption_and_recovery_completeness"
    )
    CROSS_ORGANIZATION_ISOLATION = "cross_organization_isolation"
    LATENCY_AND_RESOURCE_BUDGETS = "latency_and_resource_budgets"
    HUMAN_USEFULNESS_AND_CORRECTION_RATE = "human_usefulness_and_correction_rate"


class EvaluationCaseKind(StrEnum):
    """SS24: "evaluation sets include normal, ambiguous, stale, conflicting, adversarial,
    permission-denied, dependency-failure, and cancellation cases.\""""

    NORMAL = "normal"
    AMBIGUOUS = "ambiguous"
    STALE = "stale"
    CONFLICTING = "conflicting"
    ADVERSARIAL = "adversarial"
    PERMISSION_DENIED = "permission_denied"
    DEPENDENCY_FAILURE = "dependency_failure"
    CANCELLATION = "cancellation"


@dataclass(frozen=True, slots=True)
class AgentEvaluationResult:
    agent_id: str
    agent_version: int
    criterion_results: tuple[tuple[AgentEvaluationCriterion, bool], ...]
    case_kind_coverage: tuple[EvaluationCaseKind, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.agent_id, "agent_id")
        if self.agent_version < 1:
            raise ValueError("an agent evaluation result requires a positive agent version")
        evaluated_criteria = {criterion for criterion, _ in self.criterion_results}
        if evaluated_criteria != set(AgentEvaluationCriterion):
            raise ValueError("an agent evaluation result requires every evaluation criterion")
        if len(set(self.case_kind_coverage)) != len(self.case_kind_coverage):
            raise ValueError("an agent evaluation result must not repeat a case kind")

    @property
    def passed(self) -> bool:
        return all(passed for _, passed in self.criterion_results)


_ALLOWED_TRANSITIONS: dict[AgentLifecycleState, frozenset[AgentLifecycleState]] = {
    AgentLifecycleState.DRAFT: frozenset({AgentLifecycleState.EVALUATING}),
    AgentLifecycleState.EVALUATING: frozenset(
        {AgentLifecycleState.DRAFT, AgentLifecycleState.APPROVED}
    ),
    AgentLifecycleState.APPROVED: frozenset({AgentLifecycleState.ACTIVE}),
    AgentLifecycleState.ACTIVE: frozenset(
        {AgentLifecycleState.SUSPENDED, AgentLifecycleState.SUPERSEDED}
    ),
    AgentLifecycleState.SUSPENDED: frozenset(
        {AgentLifecycleState.ACTIVE, AgentLifecycleState.RETIRED}
    ),
    AgentLifecycleState.SUPERSEDED: frozenset({AgentLifecycleState.RETIRED}),
    AgentLifecycleState.RETIRED: frozenset(),
}


def is_valid_transition(*, from_state: AgentLifecycleState, to_state: AgentLifecycleState) -> bool:
    """SS25's lifecycle diagram, reproduced as an explicit adjacency table."""
    return to_state in _ALLOWED_TRANSITIONS[from_state]


@dataclass(frozen=True, slots=True)
class ActivationRequirements:
    """SS25: "activation requires owner, compatible model and tools, evaluations, review, and
    rollback path.\""""

    has_owner: bool
    has_compatible_model_and_tools: bool
    evaluation: AgentEvaluationResult
    has_review: bool
    has_rollback_path: bool

    @property
    def satisfied(self) -> bool:
        return (
            self.has_owner
            and self.has_compatible_model_and_tools
            and self.evaluation.passed
            and self.has_review
            and self.has_rollback_path
        )


def require_activation_requirements(requirements: ActivationRequirements) -> None:
    if not requirements.satisfied:
        raise ValueError(
            "SS25: activation requires owner, compatible model and tools, evaluations, "
            "review, and rollback path"
        )
