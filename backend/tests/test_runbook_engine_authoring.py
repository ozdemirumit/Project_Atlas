from __future__ import annotations

import pytest

from atlas.modules.guardrails.domain.reasoning_guardrails import ConfidenceLevel
from atlas.modules.runbook_engine.domain.authoring import (
    AiProposedField,
    ChangeDiff,
    SubprocedureReference,
    can_ai_directly_approve_or_publish,
    scan_authored_content_for_prohibited_material,
)


def test_subprocedure_reference_constructs_cleanly() -> None:
    example = SubprocedureReference(
        subprocedure_runbook_id="runbook.subprocedure-example",
        pinned_version_id="runbook-version.subprocedure-example",
    )
    assert example.pinned_version_id == "runbook-version.subprocedure-example"


def change_diff(**overrides: object) -> ChangeDiff:
    defaults: dict[str, object] = {
        "from_version_id": "runbook-version.a",
        "to_version_id": "runbook-version.b",
        "changed_step_ids": ("runbook-step.example",),
        "migration_impact": "Existing plans bound to version a remain pinned to it.",
    }
    defaults.update(overrides)
    return ChangeDiff(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_change_diff_constructs_cleanly() -> None:
    example = change_diff()
    assert example.changed_step_ids == ("runbook-step.example",)


def test_change_diff_requires_two_distinct_versions() -> None:
    with pytest.raises(ValueError, match="two distinct versions"):
        change_diff(from_version_id="runbook-version.a", to_version_id="runbook-version.a")


def test_change_diff_requires_a_migration_impact_statement() -> None:
    with pytest.raises(ValueError, match="migration impact"):
        change_diff(migration_impact="   ")


def test_scan_authored_content_with_clean_text() -> None:
    assert scan_authored_content_for_prohibited_material("Restart the controller gracefully.") == ()


def test_scan_authored_content_detects_a_secret_pattern() -> None:
    detected = scan_authored_content_for_prohibited_material(
        "api_key=NOTAREALSECRETPLACEHOLDERVALUE0000"
    )
    assert detected != ()


def proposed_field(**overrides: object) -> AiProposedField:
    defaults: dict[str, object] = {
        "field_name": "vendor",
        "proposed_value": "Hitachi",
        "source_span": "Section 2, paragraph 1: 'This procedure applies to Hitachi arrays.'",
        "confidence": ConfidenceLevel.HIGH,
    }
    defaults.update(overrides)
    return AiProposedField(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_proposed_field_constructs_cleanly() -> None:
    example = proposed_field()
    assert example.confidence is ConfidenceLevel.HIGH


def test_proposed_field_requires_a_field_name() -> None:
    with pytest.raises(ValueError, match="field name"):
        proposed_field(field_name="   ")


def test_proposed_field_requires_a_proposed_value() -> None:
    with pytest.raises(ValueError, match="proposed value"):
        proposed_field(proposed_value="   ")


def test_proposed_field_requires_a_source_span() -> None:
    with pytest.raises(ValueError, match="source_span is required"):
        proposed_field(source_span="   ")


def test_ai_can_never_directly_approve_or_publish() -> None:
    assert can_ai_directly_approve_or_publish() is False
