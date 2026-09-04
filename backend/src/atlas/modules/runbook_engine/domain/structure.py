"""ATLAS-045 SS8/SS9: structured runbook contract and step contract.

SS8's fourteen sections are all treated as mandatory -- the doc lists no optional subset, only
"missing mandatory sections are explicit validation findings." Sections richer than free text
(preconditions, risk/impact, rollback/recovery, branches) get their own typed contracts in later
slices; `RunbookSection` here is deliberately the generic container SS8 itself describes before
those richer types exist, and a runbook's actual step/branch/precondition/risk/rollback objects
are the source of truth once those slices land -- this section-presence check is a coarse,
document-level completeness signal, not a replacement for validating each typed object itself.

SS9's "free-form command text is documentation, not an executable capability" is given real
teeth: a `GOVERNED_CONNECTOR` step -- the only actor kind capable of a real infrastructure
effect, per SS24's "connector dispatch ... occurs only through governed runtime services" --
cannot construct without a real `capability_id`; every other actor kind cannot carry one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.modules.identity.domain.models import validate_stable_identifier


class RunbookSectionKind(StrEnum):
    """SS8's fourteen structured-runbook sections, in the document's own order."""

    PURPOSE_AND_SCOPE = "purpose_and_scope"
    APPLICABILITY_AND_EXCLUSIONS = "applicability_and_exclusions"
    TRIGGER_AND_ENTRY_CRITERIA = "trigger_and_entry_criteria"
    REQUIRED_CONTEXT_AND_EVIDENCE = "required_context_and_evidence"
    ROLES_RESPONSIBILITIES_AND_COMMUNICATION = "roles_responsibilities_and_communication"
    PRECONDITIONS_AND_READINESS_CHECKS = "preconditions_and_readiness_checks"
    RISK_IMPACT_INTERRUPTION_AND_DURATION = "risk_impact_interruption_and_duration"
    ORDERED_STEPS_AND_BRANCHES = "ordered_steps_and_branches"
    CHECKPOINTS_AND_STOP_CONDITIONS = "checkpoints_and_stop_conditions"
    SUCCESS_AND_SERVICE_VALIDATION_CRITERIA = "success_and_service_validation_criteria"
    ROLLBACK_AND_RECOVERY = "rollback_and_recovery"
    POST_RUN_MONITORING_AND_EVIDENCE_CAPTURE = "post_run_monitoring_and_evidence_capture"
    ITSM_AND_DOCUMENTATION_UPDATES = "itsm_and_documentation_updates"
    KNOWN_FAILURE_MODES_AND_ESCALATION = "known_failure_modes_and_escalation"


@dataclass(frozen=True, slots=True)
class RunbookSection:
    kind: RunbookSectionKind
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("a runbook section requires non-empty content")


def find_missing_mandatory_sections(
    sections: tuple[RunbookSection, ...],
) -> tuple[RunbookSectionKind, ...]:
    """SS8: "missing mandatory sections are explicit validation findings." Returned in the
    document's own section order, not sorted by name."""
    present = {section.kind for section in sections}
    return tuple(kind for kind in RunbookSectionKind if kind not in present)


class RunbookStepActor(StrEnum):
    """SS9: "human, deterministic workflow, or governed connector actor.\""""

    HUMAN = "human"
    DETERMINISTIC_WORKFLOW = "deterministic_workflow"
    GOVERNED_CONNECTOR = "governed_connector"


@dataclass(frozen=True, slots=True)
class RunbookStep:
    """SS9's step contract. Branch conditions (SS10), full precondition objects (SS11), and the
    rollback/recovery procedure itself (SS13) are referenced by ID here and given their own
    types in their own slices, not embedded."""

    step_id: str
    version: int
    purpose: str
    expected_state_transition: str
    actor: RunbookStepActor
    target_selector: str | None
    capability_id: str | None
    capability_version: str | None
    capability_class: CapabilityClass
    required_role: str | None
    requires_approval: bool
    requires_change_window: bool
    instructions: str
    expected_duration_minimum_minutes: int
    expected_duration_maximum_minutes: int
    expected_result: str
    timeout_seconds: int | None
    retryable: bool
    idempotent: bool
    cancellable: bool
    stop_conditions: tuple[str, ...]
    precondition_ids: tuple[str, ...]
    rollback_or_recovery_reference: str | None
    evidence_output_references: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.step_id, "step_id")
        if self.version < 1:
            raise ValueError("a runbook step requires a positive version")
        if not self.purpose.strip():
            raise ValueError("a runbook step requires a purpose")
        if not self.expected_state_transition.strip():
            raise ValueError("a runbook step requires an expected state transition")
        if not self.instructions.strip():
            raise ValueError("a runbook step requires instructions")
        if not self.expected_result.strip():
            raise ValueError("a runbook step requires an expected result")
        if self.expected_duration_minimum_minutes < 0 or self.expected_duration_maximum_minutes < 0:
            raise ValueError("expected duration minutes must not be negative")
        if self.expected_duration_minimum_minutes > self.expected_duration_maximum_minutes:
            raise ValueError(
                "expected_duration_minimum_minutes must not exceed"
                " expected_duration_maximum_minutes"
            )
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive when present")
        is_governed_connector = self.actor is RunbookStepActor.GOVERNED_CONNECTOR
        if is_governed_connector and self.capability_id is None:
            raise ValueError(
                "SS9: free-form command text is documentation, not an executable capability -- a"
                " governed-connector step requires a capability_id"
            )
        if not is_governed_connector and self.capability_id is not None:
            raise ValueError("capability_id is only meaningful for a GOVERNED_CONNECTOR step")
