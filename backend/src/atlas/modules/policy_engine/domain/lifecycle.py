"""ATLAS-025 SS15/SS22: policy lifecycle transitions and authoring separation of duties.

SS15 lists the ten lifecycle states but does not draw a transition diagram between them -- this
module makes that call, since evaluation (slice 3) already depends on a policy set's
lifecycle_state meaning something concrete. The graph below is this module's own design, not
lifted from the document; it follows the natural reading of the state sequence (author, validate,
simulate, review, approve, schedule, activate, suspend, deprecate, retire) and SS15's own two
statements: "only approved active versions affect production decisions" and "emergency
suspension is separately authorized and audited."
"""

from __future__ import annotations

from atlas.modules.policy_engine.domain.policy_set import PolicyLifecycleState
from atlas.modules.policy_engine.domain.simulation import SimulationResult

_STATES_REQUIRING_MANDATORY_TESTS = frozenset(
    {PolicyLifecycleState.SCHEDULED, PolicyLifecycleState.ACTIVE}
)

_ALLOWED_TRANSITIONS: dict[PolicyLifecycleState, frozenset[PolicyLifecycleState]] = {
    PolicyLifecycleState.DRAFT: frozenset({PolicyLifecycleState.VALIDATING}),
    PolicyLifecycleState.VALIDATING: frozenset(
        {PolicyLifecycleState.SIMULATION, PolicyLifecycleState.DRAFT}
    ),
    PolicyLifecycleState.SIMULATION: frozenset(
        {PolicyLifecycleState.REVIEW, PolicyLifecycleState.DRAFT}
    ),
    PolicyLifecycleState.REVIEW: frozenset(
        {PolicyLifecycleState.APPROVED, PolicyLifecycleState.DRAFT}
    ),
    PolicyLifecycleState.APPROVED: frozenset(
        {PolicyLifecycleState.SCHEDULED, PolicyLifecycleState.ACTIVE}
    ),
    PolicyLifecycleState.SCHEDULED: frozenset(
        {PolicyLifecycleState.ACTIVE, PolicyLifecycleState.DEPRECATED}
    ),
    PolicyLifecycleState.ACTIVE: frozenset(
        {PolicyLifecycleState.SUSPENDED, PolicyLifecycleState.DEPRECATED}
    ),
    PolicyLifecycleState.SUSPENDED: frozenset(
        {PolicyLifecycleState.ACTIVE, PolicyLifecycleState.DEPRECATED}
    ),
    PolicyLifecycleState.DEPRECATED: frozenset({PolicyLifecycleState.RETIRED}),
    PolicyLifecycleState.RETIRED: frozenset(),
}


def is_allowed_transition(current: PolicyLifecycleState, target: PolicyLifecycleState) -> bool:
    return target in _ALLOWED_TRANSITIONS[current]


def allowed_next_states(current: PolicyLifecycleState) -> frozenset[PolicyLifecycleState]:
    return _ALLOWED_TRANSITIONS[current]


class PolicyLifecycleTransitionError(Exception):
    def __init__(self, current: PolicyLifecycleState, target: PolicyLifecycleState) -> None:
        super().__init__(f"cannot transition a policy set from {current.value} to {target.value}")
        self.current = current
        self.target = target


def require_allowed_transition(current: PolicyLifecycleState, target: PolicyLifecycleState) -> None:
    if not is_allowed_transition(current, target):
        raise PolicyLifecycleTransitionError(current, target)


class PolicyAuthoringSeparationError(Exception):
    """SS22: "one identity cannot author and approve the same material permission expansion.\""""

    def __init__(self, identity_id: str) -> None:
        super().__init__(f"{identity_id} authored this policy change and cannot also approve it")
        self.identity_id = identity_id


def require_authoring_separation(*, author_id: str, approver_id: str) -> None:
    if author_id == approver_id:
        raise PolicyAuthoringSeparationError(author_id)


class PolicyMandatoryTestFailureError(Exception):
    """SS18: "a policy package cannot activate with failing mandatory deny tests.\""""

    def __init__(self, failing_case_ids: tuple[str, ...]) -> None:
        super().__init__(
            "cannot activate a policy set with failing mandatory tests: "
            + ", ".join(failing_case_ids)
        )
        self.failing_case_ids = failing_case_ids


def require_mandatory_tests_pass(
    target: PolicyLifecycleState, simulation_result: SimulationResult
) -> None:
    """Call this alongside `require_allowed_transition` whenever `target` is SCHEDULED or ACTIVE
    (SS18's activation gate applies to both -- a scheduled activation is still an activation, just
    deferred). States that do not lead toward production (DRAFT, VALIDATING, SIMULATION, REVIEW,
    ...) are never gated here; a candidate can fail every test and still sit in REVIEW."""
    if target not in _STATES_REQUIRING_MANDATORY_TESTS:
        return
    failures = simulation_result.mandatory_failures
    if failures:
        raise PolicyMandatoryTestFailureError(tuple(result.case_id for result in failures))
