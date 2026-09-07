"""ATLAS-033 SS18/SS19/SS20/SS21: collection/buffering, routing/storage, sampling/rate control,
and retention/deletion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification
from atlas.core.structured_logging import LogCategory, LogLevel


class DeliveryPriority(StrEnum):
    """SS18: "security and error records receive higher delivery priority than verbose
    diagnostics.\""""

    HIGH = "high"
    NORMAL = "normal"


def priority_for(*, is_security: bool, is_error: bool) -> DeliveryPriority:
    return DeliveryPriority.HIGH if (is_security or is_error) else DeliveryPriority.NORMAL


@dataclass(frozen=True, slots=True)
class LocalBufferPolicy:
    """`encrypted` must be `True` to construct at all -- SS18: "local persistent buffers are
    encrypted, bounded, and use defined eviction rules.\""""

    encrypted: bool
    max_bytes: int
    eviction_rule: str

    def __post_init__(self) -> None:
        if not self.encrypted:
            raise ValueError("SS18: local persistent buffers are encrypted")
        if self.max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        if not self.eviction_rule.strip():
            raise ValueError("a local buffer policy requires an eviction rule")


def backpressure_can_consume_unbounded_application_resources() -> bool:
    """SS18: "backpressure is visible and cannot consume unbounded application resources.\""""
    return False


def collector_failure_blocks_ordinary_read_requests() -> bool:
    """SS18: "collector failure does not block ordinary read requests unless a related
    mandatory audit control also fails." The exception is a distinct, separately-modeled
    condition (`atlas.core.audit`'s own failure behavior) a caller checks before relying on this
    default."""
    return False


@dataclass(frozen=True, slots=True)
class RoutingDecisionInputs:
    """SS19: "routing uses category, severity, environment, classification, and customer
    policy.\""""

    category: LogCategory
    severity: LogLevel
    environment: str
    classification: DataClassification
    customer_policy_reference: str

    def __post_init__(self) -> None:
        if not self.environment.strip():
            raise ValueError("routing decision inputs require an environment")
        if not self.customer_policy_reference.strip():
            raise ValueError("routing decision inputs require a customer policy reference")


def cross_organization_aggregation_uses_raw_values(*, explicitly_authorized: bool) -> bool:
    """SS19: "cross-organization aggregation uses anonymized metrics unless explicitly
    authorized.\""""
    return explicitly_authorized


def audit_events_are_sampled_by_logging_pipeline() -> bool:
    """SS20: "audit events are never sampled by the logging pipeline.\""""
    return False


class MandatoryVisibilityCategory(StrEnum):
    """SS20's five categories "not probabilistically sampled.\""""

    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_DENIAL = "authorization_denial"
    SECURITY_CONTROL_FAILURE = "security_control_failure"
    C2_C5_ACTIVITY_FAILURE = "c2_c5_activity_failure"
    CRITICAL_ERROR = "critical_error"


def can_probabilistically_sample(category: MandatoryVisibilityCategory | None) -> bool:
    """SS20: a mandatory-visibility category is never probabilistically sampled; `None` (e.g. a
    repetitive success event, which carries no such category) may be."""
    return category is None


@dataclass(frozen=True, slots=True)
class SuppressionSummary:
    """SS20: "a suppression summary is emitted so absence is not mistaken for absence of
    activity.\""""

    first_occurrence_at: datetime
    suppressed_count: int
    time_range_start: datetime
    time_range_end: datetime
    representative_context: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("first_occurrence_at", self.first_occurrence_at),
            ("time_range_start", self.time_range_start),
            ("time_range_end", self.time_range_end),
        ):
            if value.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        if self.suppressed_count < 1:
            raise ValueError("suppressed_count must be positive")
        if self.time_range_end < self.time_range_start:
            raise ValueError("time_range_end must not precede time_range_start")
        if not self.representative_context.strip():
            raise ValueError("a suppression summary requires representative context")


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """SS21: "retention is based on category, environment, classification, support need, legal
    requirement, and storage capacity.\""""

    category: LogCategory
    environment: str
    classification: DataClassification
    retention_days: int
    legal_hold_reference: str | None

    def __post_init__(self) -> None:
        if not self.environment.strip():
            raise ValueError("a retention policy requires an environment")
        if self.retention_days < 1:
            raise ValueError("retention_days must be positive")


def legal_hold_applies_without_formal_mapping() -> bool:
    """SS21: "legal hold applies only when formally mapped to relevant log artifacts.\""""
    return False
