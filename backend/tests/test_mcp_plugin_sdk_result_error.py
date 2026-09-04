from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.mcp_plugin_sdk.domain.result_error import (
    CapabilityOutcomeState,
    CapabilityResult,
    ConnectorError,
    ConnectorErrorCode,
    raw_exception_is_a_public_result,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def result(**overrides: object) -> CapabilityResult:
    defaults: dict[str, object] = {
        "outcome_state": CapabilityOutcomeState.SUCCESS,
        "capability_specific_data": (("inventory_count", "42"),),
        "target_id": "target.controller-b",
        "observed_at": NOW,
        "evidence_references": ("evidence.inventory-response.2026-09-04",),
        "source_references": ("vendor-api.inventory.v1",),
        "warnings": (),
        "omissions": (),
        "freshness_seconds": 2.5,
        "side_effect_confirmation": None,
        "sanitized_vendor_diagnostic_reference": None,
        "retry_guidance": None,
        "next_step_guidance": None,
    }
    defaults.update(overrides)
    return CapabilityResult(**defaults)  # type: ignore[arg-type]


def test_result_accepts_valid_state() -> None:
    assert result().outcome_state is CapabilityOutcomeState.SUCCESS


def test_result_rejects_success_without_evidence() -> None:
    with pytest.raises(ValueError, match="without required success evidence"):
        result(evidence_references=())


def test_result_allows_failure_without_evidence() -> None:
    outcome = result(outcome_state=CapabilityOutcomeState.FAILURE, evidence_references=())
    assert outcome.outcome_state is CapabilityOutcomeState.FAILURE


def test_result_rejects_negative_freshness() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        result(freshness_seconds=-1.0)


def test_connector_error_code_has_thirteen_members() -> None:
    assert len(ConnectorErrorCode) == 13


def test_connector_error_requires_safe_summary() -> None:
    with pytest.raises(ValueError, match="requires a safe summary"):
        ConnectorError(
            code=ConnectorErrorCode.TARGET_UNAVAILABLE,
            safe_summary="",
            retryable=True,
            vendor_reference=None,
            diagnostic_evidence=(),
        )


def test_connector_error_rejects_secret_looking_summary() -> None:
    with pytest.raises(ValueError, match="raw exceptions are not public results"):
        ConnectorError(
            code=ConnectorErrorCode.AUTHENTICATION_FAILURE,
            safe_summary="Authentication failed with api_key: AKIAABCDEFGHIJKLMNOP",
            retryable=False,
            vendor_reference=None,
            diagnostic_evidence=(),
        )


def test_raw_exception_never_a_public_result() -> None:
    assert raw_exception_is_a_public_result() is False
