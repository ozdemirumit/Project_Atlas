from __future__ import annotations

import pytest

from atlas.modules.observability.domain.source_requirements import (
    AiLogSignalKind,
    ComponentLogEventKind,
    ConnectorLogFields,
    SecurityLogSignalKind,
    WorkflowLogEventKind,
    can_sample_away_from_visibility,
    private_model_reasoning_is_logged,
    raw_vendor_payloads_are_enabled_by_default,
    target_timeout_is_logged_as_success,
    workflow_can_be_logged_as_completed_when_final_result_unknown,
)


def test_component_log_event_kind_has_eight_members() -> None:
    assert len(ComponentLogEventKind) == 8


def test_can_sample_away_true_for_successful_non_material_event() -> None:
    assert (
        can_sample_away_from_visibility(is_failure=False, is_material_state_transition=False)
        is True
    )


def test_can_sample_away_false_for_failure() -> None:
    assert (
        can_sample_away_from_visibility(is_failure=True, is_material_state_transition=False)
        is False
    )


def test_can_sample_away_false_for_material_state_transition() -> None:
    assert (
        can_sample_away_from_visibility(is_failure=False, is_material_state_transition=True)
        is False
    )


def connector_fields(**overrides: object) -> ConnectorLogFields:
    defaults: dict[str, object] = {
        "package_version": "1.0.0",
        "instance_version": "1.0.0",
        "target_reference": "target.controller-b",
        "capability_id": "capability.inventory.read",
        "protocol_operation": "GET /inventory",
        "timeout_seconds": 30.0,
        "attempt": 1,
        "vendor_request_id": "vendor-request.example",
        "parser_result": "parsed_ok",
        "normalized_failure_category": None,
    }
    defaults.update(overrides)
    return ConnectorLogFields(**defaults)  # type: ignore[arg-type]


def test_connector_log_fields_accepts_valid_state() -> None:
    assert connector_fields().capability_id == "capability.inventory.read"


def test_connector_log_fields_requires_target_reference() -> None:
    with pytest.raises(ValueError, match="require target_reference"):
        connector_fields(target_reference="")


def test_connector_log_fields_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        connector_fields(timeout_seconds=0.0)


def test_target_timeout_never_logged_as_success() -> None:
    assert target_timeout_is_logged_as_success() is False


def test_raw_vendor_payloads_never_enabled_by_default() -> None:
    assert raw_vendor_payloads_are_enabled_by_default() is False


def test_workflow_log_event_kind_has_eight_members() -> None:
    assert len(WorkflowLogEventKind) == 8


def test_workflow_never_logged_as_completed_when_result_unknown() -> None:
    assert workflow_can_be_logged_as_completed_when_final_result_unknown() is False


def test_ai_log_signal_kind_has_seven_members() -> None:
    assert len(AiLogSignalKind) == 7


def test_private_model_reasoning_never_logged() -> None:
    assert private_model_reasoning_is_logged() is False


def test_security_log_signal_kind_has_nine_members() -> None:
    assert len(SecurityLogSignalKind) == 9
