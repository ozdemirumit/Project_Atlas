"""ATLAS-045 SS27: outcome and improvement.

"Improvement follows ATLAS-027 governed learning: draft revision, evidence, review, approval,
publication." That governed chain is exactly slice 1's `RunbookLifecycleState` (DRAFT -> REVIEW
-> APPROVED -> PUBLISHED) -- `outcome_as_revision_trigger` decides whether an outcome is worth
starting a new DRAFT over, rather than this module inventing a second, parallel revision
workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class StepOutcomeState(StrEnum):
    """SS27: "steps completed, skipped, failed, retried, or changed.\""""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    RETRIED = "retried"
    CHANGED = "changed"


@dataclass(frozen=True, slots=True)
class StepOutcome:
    step_id: str
    state: StepOutcomeState
    note: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.step_id, "step_id")


class FinalOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    ABORTED = "aborted"


@dataclass(frozen=True, slots=True)
class RunbookOutcomeRecord:
    """SS27's seven declared elements."""

    outcome_id: str
    runbook_id: str
    version_id: str
    plan_id: str
    target_id: str
    starting_context: str
    step_outcomes: tuple[StepOutcome, ...]
    actual_duration_minutes: int
    actual_interruption: str
    actual_impact: str
    resource_use: str
    validation_passed: bool
    rollback_used: bool
    recovery_used: bool
    final_outcome: FinalOutcome
    operator_feedback: str | None
    missing_or_ambiguous_instructions: tuple[str, ...]
    related_incident_reference: str | None
    related_problem_reference: str | None
    related_change_reference: str | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.outcome_id, "outcome_id")
        validate_stable_identifier(self.runbook_id, "runbook_id")
        validate_stable_identifier(self.version_id, "version_id")
        validate_stable_identifier(self.plan_id, "plan_id")
        validate_stable_identifier(self.target_id, "target_id")
        if not self.starting_context.strip():
            raise ValueError("an outcome record requires the starting context")
        if self.actual_duration_minutes < 0:
            raise ValueError("actual_duration_minutes must not be negative")
        if not self.actual_interruption.strip():
            raise ValueError("an outcome record requires the actual interruption")
        if not self.actual_impact.strip():
            raise ValueError("an outcome record requires the actual impact")
        if not self.resource_use.strip():
            raise ValueError("an outcome record requires the resource use")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")


def outcome_as_revision_trigger(outcome: RunbookOutcomeRecord) -> bool:
    """An outcome is worth triggering a revision draft when it reveals a real gap: the run
    failed, partially succeeded, or was aborted; missing/ambiguous instructions were reported; or
    operator feedback was given. A routine full success with no feedback is not itself a trigger."""
    return (
        outcome.final_outcome
        in (FinalOutcome.PARTIAL_SUCCESS, FinalOutcome.FAILURE, FinalOutcome.ABORTED)
        or bool(outcome.missing_or_ambiguous_instructions)
        or outcome.operator_feedback is not None
    )


def has_sufficient_outcome_history_for_broad_validation(
    outcomes: tuple[RunbookOutcomeRecord, ...], *, minimum_successful_outcomes: int
) -> bool:
    """SS27: "one successful outcome does not prove universal safety." `minimum_successful_outcomes`
    must itself be at least 2 -- a caller cannot configure this check to accept a single success
    as sufficient."""
    if minimum_successful_outcomes < 2:
        raise ValueError("minimum_successful_outcomes must be at least 2 -- one is never enough")
    successful = sum(1 for outcome in outcomes if outcome.final_outcome is FinalOutcome.SUCCESS)
    return successful >= minimum_successful_outcomes
