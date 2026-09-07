"""ATLAS-033 SS24/SS25: failure behavior and observability of logging."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


def buffer_saturation_drops_highest_priority_records_first() -> bool:
    """SS24: "buffer saturation drops lowest-priority eligible records first.\""""
    return False


@dataclass(frozen=True, slots=True)
class QuarantinedRecord:
    """SS24: "invalid schema records are quarantined with safe producer diagnostics.\""""

    record_reference: str
    safe_producer_diagnostic: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.record_reference, "record_reference")
        if not self.safe_producer_diagnostic.strip():
            raise ValueError("a quarantined record requires a safe producer diagnostic")


def logging_failure_changes_unknown_result_to_success() -> bool:
    """SS24: "logging failure never changes an unknown operation result to success.\""""
    return False


def mandatory_audit_failure_follows_the_more_permissive_log_behavior() -> bool:
    """SS24: "mandatory audit failure follows ATLAS-032, not the more permissive log
    behavior.\""""
    return False


class LoggingPipelineMetric(StrEnum):
    """SS25's eight observability-of-logging metric categories."""

    RECORDS_PRODUCED_ACCEPTED_REJECTED_SAMPLED_SUPPRESSED_DROPPED_AND_FORWARDED = (
        "records_produced_accepted_rejected_sampled_suppressed_dropped_and_forwarded"
    )
    INGESTION_AND_INDEXING_LATENCY = "ingestion_and_indexing_latency"
    BUFFER_QUEUE_AND_STORAGE_UTILIZATION = "buffer_queue_and_storage_utilization"
    PARSE_SCHEMA_REDACTION_AND_ROUTING_FAILURES = "parse_schema_redaction_and_routing_failures"
    SEARCH_AVAILABILITY_AND_QUERY_LATENCY = "search_availability_and_query_latency"
    PER_COMPONENT_LOG_SILENCE_AND_UNEXPECTED_VOLUME_CHANGES = (
        "per_component_log_silence_and_unexpected_volume_changes"
    )
    RETENTION_AND_DELETION_BACKLOG = "retention_and_deletion_backlog"
    EXTERNAL_DESTINATION_HEALTH_AND_DELIVERY_LAG = "external_destination_health_and_delivery_lag"
