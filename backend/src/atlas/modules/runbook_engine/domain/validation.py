"""ATLAS-045 SS17: validation.

Reuses Guardrails' `detect_secret_patterns` and `detect_injection_signals` for the "secret ...
and prompt-injection" portion of SS17's content scans rather than a third implementation of
either detector. "Unsafe-command" detection has no existing detector anywhere in this codebase to
reuse and is not fabricated here -- stated as an open gap, matching this codebase's established
practice of being honest about what is not yet checkable rather than inventing a shallow check.

Several SS17 categories are already enforced at construction time by earlier slices rather than
needing a separate validation pass here: a `RunbookBranch` (slice 3) cannot construct without a
path for every outcome or with `UNKNOWN` routing silently to the next step; a `RunbookPrecondition`
(slice 4) cannot construct without a freshness limit and failure behavior. Those slices' own
`__post_init__` invariants are the validation for "branch reachability ... and terminal states"
and "preconditions ... and unknown-result paths" -- this module covers what those constructors
cannot check by themselves: cross-object completeness (missing sections) and free-text content
scans (secrets, injection signals).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.guardrails.domain.prompt_injection import detect_injection_signals
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.runbook_engine.domain.structure import (
    RunbookSection,
    RunbookStep,
    find_missing_mandatory_sections,
)


class ValidationCategory(StrEnum):
    """SS17's eleven named validation categories."""

    SCHEMA_AND_SECTION_COMPLETENESS = "schema_and_section_completeness"
    IDENTIFIER_AND_REFERENCE_INTEGRITY = "identifier_and_reference_integrity"
    PRODUCT_AND_CONNECTOR_COMPATIBILITY = "product_and_connector_compatibility"
    PARAMETER_AND_TARGET_SCOPE_SAFETY = "parameter_and_target_scope_safety"
    CAPABILITY_CLASSIFICATION = "capability_classification"
    PRECONDITION_AND_CONTROL_FLOW_COMPLETENESS = "precondition_and_control_flow_completeness"
    IMPACT_AND_RECOVERY_COMPLETENESS = "impact_and_recovery_completeness"
    PERMISSION_AND_APPROVAL_REQUIREMENTS = "permission_and_approval_requirements"
    PROHIBITED_CONTENT_SCAN = "prohibited_content_scan"
    BRANCH_AND_LOOP_SAFETY = "branch_and_loop_safety"
    SOURCE_FIDELITY_AND_LABELING = "source_fidelity_and_labeling"


class ValidationSeverity(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"
    ADVISORY = "advisory"


class ValidationResolutionState(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    WAIVED = "waived"


_TERMINAL_RESOLUTION_STATES = frozenset(
    {ValidationResolutionState.RESOLVED, ValidationResolutionState.WAIVED}
)


@dataclass(frozen=True, slots=True)
class RunbookValidationFinding:
    """SS17: "validation findings have severity, evidence, owner, and resolution state.\""""

    finding_id: str
    category: ValidationCategory
    severity: ValidationSeverity
    description: str
    evidence: str
    owner: str | None
    resolution_state: ValidationResolutionState
    resolution_rationale: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.finding_id, "finding_id")
        if not self.description.strip():
            raise ValueError("a validation finding requires a description")
        if not self.evidence.strip():
            raise ValueError("a validation finding requires evidence")
        is_terminal = self.resolution_state in _TERMINAL_RESOLUTION_STATES
        if is_terminal and self.resolution_rationale is None:
            raise ValueError(
                f"a finding resolved as {self.resolution_state.value} requires a"
                " resolution_rationale"
            )
        if not is_terminal and self.resolution_rationale is not None:
            raise ValueError(
                "resolution_rationale is only meaningful once a finding is resolved or waived"
            )


def find_section_completeness_findings(
    *, sections: tuple[RunbookSection, ...], finding_id_prefix: str
) -> tuple[RunbookValidationFinding, ...]:
    """SS17: "schema and required-section completeness," built on slice 2's
    `find_missing_mandatory_sections` rather than a second completeness check."""
    missing = find_missing_mandatory_sections(sections)
    return tuple(
        RunbookValidationFinding(
            finding_id=f"{finding_id_prefix}.missing-section.{kind.value}",
            category=ValidationCategory.SCHEMA_AND_SECTION_COMPLETENESS,
            severity=ValidationSeverity.BLOCKING,
            description=f"Mandatory section '{kind.value}' is missing.",
            evidence=f"No RunbookSection with kind={kind.value} was found.",
            owner=None,
            resolution_state=ValidationResolutionState.OPEN,
            resolution_rationale=None,
        )
        for kind in missing
    )


def scan_step_for_prohibited_content(
    step: RunbookStep, *, finding_id_prefix: str
) -> tuple[RunbookValidationFinding, ...]:
    """SS17: the secret and prompt-injection portion of "secret, unsafe-command, prompt-
    injection, and prohibited-content scans." Unsafe-command detection is not covered -- no
    existing detector for it exists anywhere in this codebase to reuse."""
    findings = []
    secrets = detect_secret_patterns(step.instructions)
    if secrets:
        findings.append(
            RunbookValidationFinding(
                finding_id=f"{finding_id_prefix}.{step.step_id}.secret-pattern",
                category=ValidationCategory.PROHIBITED_CONTENT_SCAN,
                severity=ValidationSeverity.BLOCKING,
                description=f"Step '{step.step_id}' instructions match a secret pattern.",
                evidence=", ".join(secrets),
                owner=None,
                resolution_state=ValidationResolutionState.OPEN,
                resolution_rationale=None,
            )
        )
    injection_signals = detect_injection_signals(step.instructions)
    if injection_signals:
        findings.append(
            RunbookValidationFinding(
                finding_id=f"{finding_id_prefix}.{step.step_id}.injection-signal",
                category=ValidationCategory.PROHIBITED_CONTENT_SCAN,
                severity=ValidationSeverity.BLOCKING,
                description=f"Step '{step.step_id}' instructions match a prompt-injection signal.",
                evidence=", ".join(injection_signals),
                owner=None,
                resolution_state=ValidationResolutionState.OPEN,
                resolution_rationale=None,
            )
        )
    return tuple(findings)
