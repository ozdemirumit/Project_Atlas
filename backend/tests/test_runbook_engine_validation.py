from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.runbook_engine.domain.structure import (
    RunbookSection,
    RunbookSectionKind,
    RunbookStep,
    RunbookStepActor,
)
from atlas.modules.runbook_engine.domain.validation import (
    RunbookValidationFinding,
    ValidationCategory,
    ValidationResolutionState,
    ValidationSeverity,
    find_section_completeness_findings,
    scan_step_for_prohibited_content,
)


def finding(**overrides: object) -> RunbookValidationFinding:
    defaults: dict[str, object] = {
        "finding_id": "runbook-validation-finding.example",
        "category": ValidationCategory.SCHEMA_AND_SECTION_COMPLETENESS,
        "severity": ValidationSeverity.WARNING,
        "description": "The rollback section is thin.",
        "evidence": "The rollback section has one sentence of content.",
        "owner": "subject.domain-reviewer",
        "resolution_state": ValidationResolutionState.OPEN,
        "resolution_rationale": None,
    }
    defaults.update(overrides)
    return RunbookValidationFinding(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_finding_constructs_cleanly() -> None:
    example = finding()
    assert example.resolution_state is ValidationResolutionState.OPEN


def test_rejects_blank_description() -> None:
    with pytest.raises(ValueError, match="description"):
        finding(description="   ")


def test_rejects_blank_evidence() -> None:
    with pytest.raises(ValueError, match="evidence"):
        finding(evidence="   ")


def test_resolved_state_requires_a_rationale() -> None:
    with pytest.raises(ValueError, match="requires a"):
        finding(resolution_state=ValidationResolutionState.RESOLVED, resolution_rationale=None)


def test_waived_state_requires_a_rationale() -> None:
    with pytest.raises(ValueError, match="requires a"):
        finding(resolution_state=ValidationResolutionState.WAIVED, resolution_rationale=None)


def test_resolved_state_constructs_with_a_rationale() -> None:
    example = finding(
        resolution_state=ValidationResolutionState.RESOLVED,
        resolution_rationale="The section was expanded with rollback steps.",
    )
    assert example.resolution_rationale is not None


def test_open_state_cannot_carry_a_rationale() -> None:
    with pytest.raises(ValueError, match="only meaningful once"):
        finding(
            resolution_state=ValidationResolutionState.OPEN,
            resolution_rationale="Not yet applicable.",
        )


def section(**overrides: object) -> RunbookSection:
    defaults: dict[str, object] = {
        "kind": RunbookSectionKind.PURPOSE_AND_SCOPE,
        "content": "Restore redundancy after a single-controller degradation event.",
    }
    defaults.update(overrides)
    return RunbookSection(**defaults)  # type: ignore[arg-type]


def test_find_section_completeness_findings_with_all_sections_present() -> None:
    sections = tuple(section(kind=kind) for kind in RunbookSectionKind)
    findings = find_section_completeness_findings(
        sections=sections, finding_id_prefix="runbook-validation"
    )
    assert findings == ()


def test_find_section_completeness_findings_reports_missing_sections() -> None:
    present = tuple(
        section(kind=kind)
        for kind in RunbookSectionKind
        if kind is not RunbookSectionKind.ROLLBACK_AND_RECOVERY
    )
    findings = find_section_completeness_findings(
        sections=present, finding_id_prefix="runbook-validation"
    )
    assert len(findings) == 1
    assert findings[0].category is ValidationCategory.SCHEMA_AND_SECTION_COMPLETENESS
    assert findings[0].severity is ValidationSeverity.BLOCKING


def step(**overrides: object) -> RunbookStep:
    defaults: dict[str, object] = {
        "step_id": "runbook-step.example",
        "version": 1,
        "purpose": "Restart controller B.",
        "expected_state_transition": "Controller B moves from degraded to healthy.",
        "actor": RunbookStepActor.HUMAN,
        "target_selector": "target.example",
        "capability_id": None,
        "capability_version": None,
        "capability_class": CapabilityClass.C1_READ_ONLY,
        "required_role": None,
        "requires_approval": False,
        "requires_change_window": False,
        "instructions": "Issue a graceful restart to controller B and monitor for recovery.",
        "expected_duration_minimum_minutes": 1,
        "expected_duration_maximum_minutes": 5,
        "expected_result": "Controller B reports healthy status.",
        "timeout_seconds": 600,
        "retryable": False,
        "idempotent": False,
        "cancellable": True,
        "stop_conditions": (),
        "precondition_ids": (),
        "rollback_or_recovery_reference": None,
        "evidence_output_references": (),
    }
    defaults.update(overrides)
    return RunbookStep(**defaults)  # type: ignore[arg-type]


def test_scan_step_for_prohibited_content_with_clean_instructions() -> None:
    findings = scan_step_for_prohibited_content(step(), finding_id_prefix="runbook-validation")
    assert findings == ()


def test_scan_step_for_prohibited_content_detects_a_secret_pattern() -> None:
    example = step(instructions="Authenticate first: api_key=NOTAREALSECRETPLACEHOLDERVALUE0000")
    findings = scan_step_for_prohibited_content(example, finding_id_prefix="runbook-validation")
    assert any(f.category is ValidationCategory.PROHIBITED_CONTENT_SCAN for f in findings)
