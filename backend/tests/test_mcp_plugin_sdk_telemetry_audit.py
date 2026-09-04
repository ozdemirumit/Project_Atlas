from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.mcp_plugin_sdk.domain.telemetry_audit import (
    AuditMetadataSubmission,
    MetricLabelConstraint,
    TelemetryEvent,
    TelemetryMetadata,
    connector_handlers_write_directly_to_audit_store,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def metadata(**overrides: object) -> TelemetryMetadata:
    defaults: dict[str, object] = {
        "component": "connector-runner",
        "connector_id": "connector.example.storage",
        "instance_reference": "connector-instance.example",
        "capability_id": "capability.inventory.read",
        "invocation_id": "invocation.example",
        "attempt": 1,
        "correlation_id": "correlation.example",
        "trace_id": "trace.example",
    }
    defaults.update(overrides)
    return TelemetryMetadata(**defaults)  # type: ignore[arg-type]


def test_telemetry_metadata_accepts_valid_state() -> None:
    assert metadata().component == "connector-runner"


def test_telemetry_metadata_requires_positive_attempt() -> None:
    with pytest.raises(ValueError, match="positive, 1-based attempt"):
        metadata(attempt=0)


def test_telemetry_event_requires_name() -> None:
    with pytest.raises(ValueError, match="requires a name"):
        TelemetryEvent(event_name="", safe_fields=())


def test_telemetry_event_rejects_secret_looking_field() -> None:
    with pytest.raises(ValueError, match="rejects or redacts secret values"):
        TelemetryEvent(
            event_name="capability.invoked",
            safe_fields=(("api_key", "AKIAABCDEFGHIJKLMNOP"),),
        )


def test_telemetry_event_accepts_safe_field() -> None:
    event = TelemetryEvent(
        event_name="capability.invoked", safe_fields=(("target_id", "target.controller-b"),)
    )
    assert event.event_name == "capability.invoked"


def test_metric_label_constraint_is_allowed() -> None:
    constraint = MetricLabelConstraint(
        allowed_label_names=frozenset({"capability_id", "outcome"}), max_cardinality=100
    )
    assert constraint.is_allowed("capability_id") is True
    assert constraint.is_allowed("free_text_message") is False


def test_metric_label_constraint_requires_at_least_one_label() -> None:
    with pytest.raises(ValueError, match="at least one allowed label"):
        MetricLabelConstraint(allowed_label_names=frozenset(), max_cardinality=10)


def test_connector_handlers_never_write_directly_to_audit_store() -> None:
    assert connector_handlers_write_directly_to_audit_store() is False


def submission(**overrides: object) -> AuditMetadataSubmission:
    defaults: dict[str, object] = {
        "target_id": "target.controller-b",
        "capability_id": "capability.inventory.read",
        "evidence_references": ("evidence.inventory-response.2026-09-04",),
        "sanitized_parameter_summary": "target=target.controller-b, mode=full",
        "vendor_operation_reference": "vendor.op.get-inventory",
        "side_effect_confirmation": None,
        "outcome_confirmation": "42 volumes returned",
        "source_observation_time": NOW,
        "partial_or_uncertain_outcome_detail": None,
    }
    defaults.update(overrides)
    return AuditMetadataSubmission(**defaults)  # type: ignore[arg-type]


def test_submission_accepts_valid_state() -> None:
    assert submission().capability_id == "capability.inventory.read"


def test_submission_requires_evidence_references() -> None:
    with pytest.raises(ValueError, match="requires evidence references"):
        submission(evidence_references=())


def test_submission_rejects_secret_looking_parameter_summary() -> None:
    with pytest.raises(ValueError, match="secret-looking content"):
        submission(sanitized_parameter_summary="api_key: AKIAABCDEFGHIJKLMNOP")


def test_submission_requires_timezone_aware_observation_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        submission(source_observation_time=datetime(2026, 9, 4, 12, 0))
