from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.classification import DataClassification
from atlas.core.structured_logging import LogCategory, LogLevel
from atlas.modules.observability.domain.pipeline import (
    DeliveryPriority,
    LocalBufferPolicy,
    MandatoryVisibilityCategory,
    RetentionPolicy,
    RoutingDecisionInputs,
    SuppressionSummary,
    audit_events_are_sampled_by_logging_pipeline,
    backpressure_can_consume_unbounded_application_resources,
    can_probabilistically_sample,
    collector_failure_blocks_ordinary_read_requests,
    cross_organization_aggregation_uses_raw_values,
    legal_hold_applies_without_formal_mapping,
    priority_for,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def test_priority_for_security_is_high() -> None:
    assert priority_for(is_security=True, is_error=False) is DeliveryPriority.HIGH


def test_priority_for_error_is_high() -> None:
    assert priority_for(is_security=False, is_error=True) is DeliveryPriority.HIGH


def test_priority_for_verbose_diagnostic_is_normal() -> None:
    assert priority_for(is_security=False, is_error=False) is DeliveryPriority.NORMAL


def test_local_buffer_policy_requires_encryption() -> None:
    with pytest.raises(ValueError, match="are encrypted"):
        LocalBufferPolicy(encrypted=False, max_bytes=1000, eviction_rule="oldest_first")


def test_backpressure_never_consumes_unbounded_resources() -> None:
    assert backpressure_can_consume_unbounded_application_resources() is False


def test_collector_failure_never_blocks_ordinary_reads_by_default() -> None:
    assert collector_failure_blocks_ordinary_read_requests() is False


def test_routing_decision_inputs_requires_environment() -> None:
    with pytest.raises(ValueError, match="require an environment"):
        RoutingDecisionInputs(
            category=LogCategory.API_AND_REQUEST_PROCESSING,
            severity=LogLevel.INFO,
            environment="",
            classification=DataClassification.INTERNAL,
            customer_policy_reference="policy.default",
        )


def test_cross_organization_aggregation_requires_explicit_authorization() -> None:
    assert cross_organization_aggregation_uses_raw_values(explicitly_authorized=False) is False
    assert cross_organization_aggregation_uses_raw_values(explicitly_authorized=True) is True


def test_audit_events_never_sampled() -> None:
    assert audit_events_are_sampled_by_logging_pipeline() is False


def test_can_probabilistically_sample_false_for_mandatory_category() -> None:
    assert can_probabilistically_sample(MandatoryVisibilityCategory.CRITICAL_ERROR) is False


def test_can_probabilistically_sample_true_for_no_category() -> None:
    assert can_probabilistically_sample(None) is True


def test_suppression_summary_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        SuppressionSummary(
            first_occurrence_at=NOW,
            suppressed_count=5,
            time_range_start=NOW,
            time_range_end=NOW - timedelta(minutes=1),
            representative_context="Repeated health-check retries.",
        )


def test_suppression_summary_requires_positive_count() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        SuppressionSummary(
            first_occurrence_at=NOW,
            suppressed_count=0,
            time_range_start=NOW,
            time_range_end=NOW + timedelta(minutes=1),
            representative_context="Repeated health-check retries.",
        )


def test_retention_policy_requires_positive_days() -> None:
    with pytest.raises(ValueError, match="retention_days must be positive"):
        RetentionPolicy(
            category=LogCategory.API_AND_REQUEST_PROCESSING,
            environment="production",
            classification=DataClassification.INTERNAL,
            retention_days=0,
            legal_hold_reference=None,
        )


def test_legal_hold_never_applies_without_formal_mapping() -> None:
    assert legal_hold_applies_without_formal_mapping() is False
