from __future__ import annotations

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.runbook_engine.domain.structure import (
    RunbookSection,
    RunbookSectionKind,
    RunbookStep,
    RunbookStepActor,
    find_missing_mandatory_sections,
)


def section(**overrides: object) -> RunbookSection:
    defaults: dict[str, object] = {
        "kind": RunbookSectionKind.PURPOSE_AND_SCOPE,
        "content": "Restore redundancy after a single-controller degradation event.",
    }
    defaults.update(overrides)
    return RunbookSection(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_section_constructs_cleanly() -> None:
    example = section()
    assert example.kind is RunbookSectionKind.PURPOSE_AND_SCOPE


def test_a_section_requires_non_empty_content() -> None:
    with pytest.raises(ValueError, match="non-empty content"):
        section(content="   ")


def test_find_missing_mandatory_sections_with_all_present_returns_empty() -> None:
    sections = tuple(section(kind=kind) for kind in RunbookSectionKind)
    assert find_missing_mandatory_sections(sections) == ()


def test_find_missing_mandatory_sections_reports_every_absent_kind() -> None:
    present = tuple(
        section(kind=kind)
        for kind in RunbookSectionKind
        if kind is not RunbookSectionKind.ROLLBACK_AND_RECOVERY
        and kind is not RunbookSectionKind.KNOWN_FAILURE_MODES_AND_ESCALATION
    )
    missing = find_missing_mandatory_sections(present)
    assert set(missing) == {
        RunbookSectionKind.ROLLBACK_AND_RECOVERY,
        RunbookSectionKind.KNOWN_FAILURE_MODES_AND_ESCALATION,
    }


def test_find_missing_mandatory_sections_with_no_sections_returns_all_fourteen() -> None:
    assert len(find_missing_mandatory_sections(())) == 14


def step(**overrides: object) -> RunbookStep:
    defaults: dict[str, object] = {
        "step_id": "runbook-step.example",
        "version": 1,
        "purpose": "Restart controller B.",
        "expected_state_transition": "Controller B moves from degraded to healthy.",
        "actor": RunbookStepActor.GOVERNED_CONNECTOR,
        "target_selector": "target.example",
        "capability_id": "capability.storage.controller.restart",
        "capability_version": "1",
        "capability_class": CapabilityClass.C3_CONTROLLED_CHANGE,
        "required_role": "role.storage-operator",
        "requires_approval": True,
        "requires_change_window": False,
        "instructions": "Issue a graceful restart to controller B and monitor for recovery.",
        "expected_duration_minimum_minutes": 1,
        "expected_duration_maximum_minutes": 5,
        "expected_result": "Controller B reports healthy status.",
        "timeout_seconds": 600,
        "retryable": False,
        "idempotent": False,
        "cancellable": True,
        "stop_conditions": ("The redundant path also reports degraded.",),
        "precondition_ids": ("runbook-precondition.example",),
        "rollback_or_recovery_reference": "runbook-recovery.example",
        "evidence_output_references": ("evidence.example",),
    }
    defaults.update(overrides)
    return RunbookStep(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_step_constructs_cleanly() -> None:
    example = step()
    assert example.actor is RunbookStepActor.GOVERNED_CONNECTOR


def test_governed_connector_step_requires_a_capability_id() -> None:
    with pytest.raises(ValueError, match="requires a capability_id"):
        step(capability_id=None)


def test_human_step_cannot_carry_a_capability_id() -> None:
    with pytest.raises(ValueError, match="only meaningful for a GOVERNED_CONNECTOR"):
        step(actor=RunbookStepActor.HUMAN, capability_id="capability.example")


def test_human_step_constructs_without_a_capability_id() -> None:
    example = step(actor=RunbookStepActor.HUMAN, capability_id=None, capability_version=None)
    assert example.capability_id is None


def test_deterministic_workflow_step_cannot_carry_a_capability_id() -> None:
    with pytest.raises(ValueError, match="only meaningful for a GOVERNED_CONNECTOR"):
        step(actor=RunbookStepActor.DETERMINISTIC_WORKFLOW, capability_id="capability.example")


def test_rejects_non_positive_version() -> None:
    with pytest.raises(ValueError, match="positive version"):
        step(version=0)


def test_rejects_blank_purpose() -> None:
    with pytest.raises(ValueError, match="purpose"):
        step(purpose="   ")


def test_rejects_blank_instructions() -> None:
    with pytest.raises(ValueError, match="instructions"):
        step(instructions="   ")


def test_rejects_duration_minimum_exceeding_maximum() -> None:
    with pytest.raises(ValueError, match="expected_duration_minimum_minutes"):
        step(expected_duration_minimum_minutes=10, expected_duration_maximum_minutes=5)


def test_rejects_negative_duration_minutes() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        step(expected_duration_minimum_minutes=-1)


def test_rejects_non_positive_timeout_when_present() -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        step(timeout_seconds=0)


def test_timeout_may_be_none() -> None:
    example = step(timeout_seconds=None)
    assert example.timeout_seconds is None
