from __future__ import annotations

import pytest

from atlas.modules.guardrails.domain.tool_result_guardrails import (
    ResultLimits,
    ToolResult,
    ToolResultState,
    normalize_result_state,
    requires_incident,
    validate_result,
)


def result(**overrides: object) -> ToolResult:
    defaults: dict[str, object] = {
        "result_id": "tool-result.example",
        "tool_id": "tool.storage-health-read",
        "state": ToolResultState.SUCCESS,
        "size_bytes": 100,
        "vendor_status": "ok",
        "external_request_id": "vendor-request.example",
        "returned_target_id": "target.example",
        "requested_target_id": "target.example",
        "unexpected_side_effect_detected": False,
    }
    defaults.update(overrides)
    return ToolResult(**defaults)  # type: ignore[arg-type]


def test_a_matching_target_has_no_mismatch() -> None:
    assert result().target_mismatch is False


def test_a_returned_target_different_from_requested_is_a_mismatch() -> None:
    example = result(returned_target_id="target.other")
    assert example.target_mismatch is True


def test_a_missing_returned_target_is_not_treated_as_a_mismatch() -> None:
    example = result(returned_target_id=None)
    assert example.target_mismatch is False


def test_size_bytes_rejects_a_negative_value() -> None:
    with pytest.raises(ValueError, match="size_bytes"):
        result(size_bytes=-1)


@pytest.mark.parametrize("model_claims_success", [True, False])
def test_normalize_result_state_ignores_the_model_claim(model_claims_success: bool) -> None:
    example = result(state=ToolResultState.TIMEOUT)
    assert (
        normalize_result_state(example, model_summary_claims_success=model_claims_success)
        is ToolResultState.TIMEOUT
    )


def test_a_clean_result_within_limits_has_no_violations() -> None:
    assert validate_result(result(), limits=ResultLimits(max_size_bytes=1000)) == ()


def test_an_oversized_result_is_a_violation() -> None:
    violations = validate_result(result(size_bytes=2000), limits=ResultLimits(max_size_bytes=1000))
    assert len(violations) == 1


def test_a_target_mismatch_is_a_violation() -> None:
    violations = validate_result(
        result(returned_target_id="target.other"), limits=ResultLimits(max_size_bytes=1000)
    )
    assert any("does not match" in v for v in violations)


def test_an_unexpected_side_effect_is_a_violation() -> None:
    violations = validate_result(
        result(unexpected_side_effect_detected=True), limits=ResultLimits(max_size_bytes=1000)
    )
    assert any("side effect" in v for v in violations)


def test_multiple_violations_are_all_reported() -> None:
    violations = validate_result(
        result(
            size_bytes=2000,
            returned_target_id="target.other",
            unexpected_side_effect_detected=True,
        ),
        limits=ResultLimits(max_size_bytes=1000),
    )
    assert len(violations) == 3


def test_requires_incident_for_an_unexpected_side_effect() -> None:
    assert requires_incident(result(unexpected_side_effect_detected=True)) is True


def test_requires_incident_for_a_target_mismatch() -> None:
    assert requires_incident(result(returned_target_id="target.other")) is True


def test_no_incident_required_for_a_clean_result() -> None:
    assert requires_incident(result()) is False


def test_result_limits_reject_a_non_positive_max_size() -> None:
    with pytest.raises(ValueError, match="max_size_bytes"):
        ResultLimits(max_size_bytes=0)
