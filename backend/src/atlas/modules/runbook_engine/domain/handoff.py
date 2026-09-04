"""ATLAS-045 SS24/SS25: execution boundary and human handoff.

`RunbookHandoffView` aggregates what earlier slices already built (preconditions, steps,
branches, risk/impact, rollback/recovery, applicability) rather than a second capture of any of
them -- matching the aggregator pattern `explainability.investigation_presentation.
InvestigationPresentation` already established for a similarly broad SS20 view.

SS24's execution-boundary rules are largely platform-wide guarantees already enforced elsewhere
in this codebase (Policy Engine's `NonOverridableRule.C5_AUTONOMOUS_EXECUTION`; no module in this
codebase gives an LLM arbitrary execution or infrastructure credentials) rather than something
Runbook Engine needs to re-model; `is_available_to_autonomous_ai` covers the one rule that is
genuinely this module's own to check -- which capability classes a runbook step may carry when
driven autonomously.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.runbook_engine.domain.applicability import ApplicabilityMatch
from atlas.modules.runbook_engine.domain.branching import RunbookBranch
from atlas.modules.runbook_engine.domain.preconditions import RunbookPrecondition
from atlas.modules.runbook_engine.domain.risk_impact import RunbookRiskImpactDuration
from atlas.modules.runbook_engine.domain.rollback_recovery import RunbookRollbackOrRecovery
from atlas.modules.runbook_engine.domain.structure import RunbookStep

_AUTONOMOUS_ELIGIBLE_CLASSES = frozenset(
    {
        CapabilityClass.C0_INFORMATIONAL,
        CapabilityClass.C1_READ_ONLY,
        CapabilityClass.C2_DIAGNOSTIC,
    }
)


def is_available_to_autonomous_ai(capability_class: CapabilityClass) -> bool:
    """SS24: "C3-C5 steps remain unavailable to autonomous AI.\""""
    return capability_class in _AUTONOMOUS_ELIGIBLE_CLASSES


class OperatorRecordKind(StrEnum):
    ACTUAL_RESULT = "actual_result"
    DEVIATION = "deviation"


@dataclass(frozen=True, slots=True)
class OperatorRecordedResult:
    """SS25: "operators can record actual results and deviations without silently editing the
    runbook." Reference-only, matching the "never mutates the source" structural pattern
    `explainability.investigation_presentation.InvestigationAnnotation` and
    `explainability.challenge_and_correction.ChallengeOrCorrection` already established -- this
    carries a `step_id` reference plus its own identity/attribution/timestamp, with no field
    through which recording one could touch the runbook step it references."""

    record_id: str
    step_id: str
    kind: OperatorRecordKind
    recorded_by: str
    recorded_at: datetime
    actual_result: str
    deviation_note: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.record_id, "record_id")
        validate_stable_identifier(self.step_id, "step_id")
        if not self.recorded_by.strip():
            raise ValueError("an operator-recorded result requires who recorded it")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        if not self.actual_result.strip():
            raise ValueError("an operator-recorded result requires the actual result")
        is_deviation = self.kind is OperatorRecordKind.DEVIATION
        if is_deviation and self.deviation_note is None:
            raise ValueError("a DEVIATION record requires a deviation_note")
        if not is_deviation and self.deviation_note is not None:
            raise ValueError("deviation_note is only meaningful for a DEVIATION record")


@dataclass(frozen=True, slots=True)
class RunbookHandoffView:
    """SS25's nine handoff-view elements."""

    runbook_id: str
    version_id: str
    plan_id: str
    target_id: str
    environment_id: str
    applicability: ApplicabilityMatch
    roles_and_responsibilities: tuple[tuple[str, str], ...]
    preconditions: tuple[RunbookPrecondition, ...]
    steps: tuple[RunbookStep, ...]
    branches: tuple[RunbookBranch, ...]
    risk_impact: RunbookRiskImpactDuration
    rollback_and_recovery: tuple[RunbookRollbackOrRecovery, ...]
    required_approval_reference: str | None
    itsm_context_reference: str | None
    evidence_capture_checklist: tuple[str, ...]
    service_validation_checklist: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.runbook_id, "runbook_id")
        validate_stable_identifier(self.version_id, "version_id")
        validate_stable_identifier(self.plan_id, "plan_id")
        validate_stable_identifier(self.target_id, "target_id")
        validate_stable_identifier(self.environment_id, "environment_id")
        if not self.steps:
            raise ValueError("a handoff view requires at least one ordered step")
