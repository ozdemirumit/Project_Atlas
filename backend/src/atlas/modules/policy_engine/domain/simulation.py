"""ATLAS-025 SS17: policy simulation.

"Simulation never authorizes or executes the represented operations" -- trivially true here,
since `evaluate_policy` is already a pure function with no I/O or side effect. Simulation is just
running curated cases through it and comparing outcomes; there is no separate execution path to
accidentally trigger.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.policy_engine.domain.evaluation import evaluate_policy
from atlas.modules.policy_engine.domain.models import PolicyDecisionOutcome, PolicyDecisionRequest
from atlas.modules.policy_engine.domain.policy_set import PolicySet


@dataclass(frozen=True, slots=True)
class SimulationCase:
    """One curated request and the outcome it is expected to produce (SS17: "curated allow and
    deny cases" -- this type is deliberately generic enough to also express SS17's other six
    named categories: sanitized historical decisions replayed as cases, one case per capability
    class, cross-boundary attempts, every non-VALID approval status, and so on)."""

    case_id: str
    request: PolicyDecisionRequest
    expected_outcome: PolicyDecisionOutcome

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("a simulation case requires an identifier")


@dataclass(frozen=True, slots=True)
class SimulationCaseResult:
    case_id: str
    expected_outcome: PolicyDecisionOutcome
    actual_outcome: PolicyDecisionOutcome

    @property
    def passed(self) -> bool:
        return self.actual_outcome is self.expected_outcome


@dataclass(frozen=True, slots=True)
class SimulationResult:
    case_results: tuple[SimulationCaseResult, ...]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.case_results)

    @property
    def failures(self) -> tuple[SimulationCaseResult, ...]:
        return tuple(result for result in self.case_results if not result.passed)


def simulate_policy(
    cases: tuple[SimulationCase, ...],
    candidate_policy_sets: tuple[PolicySet, ...],
    *,
    decided_at: datetime,
) -> SimulationResult:
    """Runs every case's request through `evaluate_policy` against `candidate_policy_sets` and
    compares the outcome to what the case declares it expects."""
    results = tuple(
        SimulationCaseResult(
            case_id=case.case_id,
            expected_outcome=case.expected_outcome,
            actual_outcome=evaluate_policy(
                case.request,
                candidate_policy_sets,
                decision_id=f"policy-decision.simulation.{case.case_id}",
                decided_at=decided_at,
            ).outcome,
        )
        for case in cases
    )
    return SimulationResult(case_results=results)


def find_outcome_regressions(
    cases: tuple[SimulationCase, ...],
    *,
    baseline_policy_sets: tuple[PolicySet, ...],
    candidate_policy_sets: tuple[PolicySet, ...],
    decided_at: datetime,
) -> tuple[str, ...]:
    """SS16's "before and after semantic diff" applied to real cases rather than rule text: for
    each case, evaluates it against both the currently-active (baseline) and the candidate policy
    sets and returns every case_id whose outcome would change. An empty tuple means the candidate
    changes nothing observable across these cases -- it does not mean the candidate is otherwise
    safe, only that these specific curated cases see no difference."""
    changed: list[str] = []
    for case in cases:
        baseline_outcome = evaluate_policy(
            case.request,
            baseline_policy_sets,
            decision_id=f"policy-decision.baseline.{case.case_id}",
            decided_at=decided_at,
        ).outcome
        candidate_outcome = evaluate_policy(
            case.request,
            candidate_policy_sets,
            decision_id=f"policy-decision.candidate.{case.case_id}",
            decided_at=decided_at,
        ).outcome
        if baseline_outcome is not candidate_outcome:
            changed.append(case.case_id)
    return tuple(changed)
