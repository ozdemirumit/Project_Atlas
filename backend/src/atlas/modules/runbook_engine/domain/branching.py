"""ATLAS-045 SS10: branch and decision contract.

`branch_broadens_capability_class` and `requires_policy_reevaluation` are exposed as functions
rather than constructor-time invariants on `BranchPath`/`RunbookBranch`, since answering "does
this branch broaden capability class" or "is this a consequential boundary" requires seeing both
the originating and destination `RunbookStep` objects (from slice 2) -- something a branch's own
constructor never has in hand. Target-scope broadening ("branches cannot broaden target scope")
is not checked here: `RunbookStep.target_selector` is a plain string with no structured subset/
superset relationship modeled anywhere yet, so a real check would have to guess at string
containment rather than verify actual scope -- stated as a gap rather than faked.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.core.capabilities import FOUNDATION_CAPABILITY_CLASSES, CapabilityClass
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.runbook_engine.domain.structure import RunbookStep


class BranchOutcome(StrEnum):
    """SS10: "expected true, false, unknown, timeout, and error paths are declared.\""""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    ERROR = "error"


class BranchDestination(StrEnum):
    NEXT_STEP = "next_step"
    ROUTE_TO_REVIEW = "route_to_review"
    SAFE_STOP = "safe_stop"


@dataclass(frozen=True, slots=True)
class BranchCondition:
    """SS10: "branch conditions use typed observable fields where possible." `comparison` stays a
    plain string (e.g. "equals", "greater_than") for MVP rather than a full expression language,
    matching SS33's "structured YAML/JSON... selected by ADR" MVP posture -- not yet decided in
    this codebase."""

    observed_field: str
    comparison: str
    expected_value: str

    def __post_init__(self) -> None:
        if not self.observed_field.strip():
            raise ValueError("a branch condition requires an observed field")
        if not self.comparison.strip():
            raise ValueError("a branch condition requires a comparison")
        if not self.expected_value.strip():
            raise ValueError("a branch condition requires an expected value")


@dataclass(frozen=True, slots=True)
class BranchPath:
    outcome: BranchOutcome
    destination: BranchDestination
    next_step_id: str | None

    def __post_init__(self) -> None:
        is_next_step = self.destination is BranchDestination.NEXT_STEP
        if is_next_step and self.next_step_id is None:
            raise ValueError("a branch path routing to the next step requires next_step_id")
        if not is_next_step and self.next_step_id is not None:
            raise ValueError("next_step_id is only meaningful when destination is NEXT_STEP")


@dataclass(frozen=True, slots=True)
class RunbookBranch:
    branch_id: str
    step_id: str
    condition: BranchCondition
    paths: tuple[BranchPath, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.branch_id, "branch_id")
        validate_stable_identifier(self.step_id, "step_id")
        outcomes = tuple(path.outcome for path in self.paths)
        if len(set(outcomes)) != len(outcomes):
            raise ValueError("a runbook branch cannot declare more than one path per outcome")
        missing = set(BranchOutcome) - set(outcomes)
        if missing:
            raise ValueError(
                "SS10: expected true, false, unknown, timeout, and error paths are declared --"
                f" missing {sorted(outcome.value for outcome in missing)}"
            )
        unknown_path = next(path for path in self.paths if path.outcome is BranchOutcome.UNKNOWN)
        if unknown_path.destination is BranchDestination.NEXT_STEP:
            raise ValueError(
                "SS10: unknown or ambiguous result routes to review or a safe stop, never"
                " silently to the next step"
            )


@dataclass(frozen=True, slots=True)
class RunbookLoop:
    """SS10: "loops have maximum iterations, deadline, and exit conditions.\""""

    loop_id: str
    maximum_iterations: int
    deadline_seconds: int
    exit_conditions: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.loop_id, "loop_id")
        if self.maximum_iterations < 1:
            raise ValueError("a runbook loop requires at least one maximum iteration")
        if self.deadline_seconds < 1:
            raise ValueError("a runbook loop requires a positive deadline")
        if not self.exit_conditions:
            raise ValueError("a runbook loop requires at least one exit condition")


_CAPABILITY_CLASS_RANK: dict[CapabilityClass, int] = {
    CapabilityClass.C0_INFORMATIONAL: 0,
    CapabilityClass.C1_READ_ONLY: 1,
    CapabilityClass.C2_DIAGNOSTIC: 2,
    CapabilityClass.C3_CONTROLLED_CHANGE: 3,
    CapabilityClass.C4_SERVICE_IMPACTING: 4,
    CapabilityClass.C5_DESTRUCTIVE: 5,
}


def branch_broadens_capability_class(*, from_step: RunbookStep, to_step: RunbookStep) -> bool:
    """SS10: "branches cannot broaden target scope or capability class." True when the
    destination step's capability class outranks the originating step's."""
    return (
        _CAPABILITY_CLASS_RANK[to_step.capability_class]
        > _CAPABILITY_CLASS_RANK[from_step.capability_class]
    )


def requires_policy_reevaluation(*, to_step: RunbookStep) -> bool:
    """SS10: "policy and approval are re-evaluated at consequential boundaries." A destination
    step is a consequential boundary when its capability class is above the foundation
    (informational/read-only) tier -- reusing
    `atlas.core.capabilities.FOUNDATION_CAPABILITY_CLASSES` rather than a second threshold -- or
    when it explicitly requires approval."""
    return (
        to_step.capability_class not in FOUNDATION_CAPABILITY_CLASSES or to_step.requires_approval
    )
