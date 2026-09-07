"""ATLAS-033 SS13/SS14/SS15/SS16/SS17: per-source logging requirements.

SS13/SS15/SS16/SS17 each read as "logs from this source include these categories of events" --
enums, since these are event *kinds* a source must be able to emit, not fields every single record
carries. SS14 reads differently -- "connector logs include [a literal field list]" -- so
`ConnectorLogFields` is a dataclass matching that field list directly, the same distinction
`core.structured_logging.StructuredLogRecord` draws between its own field groups.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ComponentLogEventKind(StrEnum):
    """SS13's eight required component logging events."""

    STARTUP_VERSION_CONFIG_SOURCE_READINESS_AND_SHUTDOWN = (
        "startup_version_config_source_readiness_and_shutdown"
    )
    DEPENDENCY_CONNECTION_STATE_AND_BOUNDED_RETRY = "dependency_connection_state_and_bounded_retry"
    REQUEST_OUTCOME_ERROR_CODE_AND_DURATION = "request_outcome_error_code_and_duration"
    QUEUE_OR_WORK_ITEM_TRANSITION_AND_ATTEMPT = "queue_or_work_item_transition_and_attempt"
    RESOURCE_EXHAUSTION_BACKPRESSURE_AND_DEGRADED_MODE = (
        "resource_exhaustion_backpressure_and_degraded_mode"
    )
    CONFIGURATION_RELOAD_AND_COMPATIBILITY_WARNING = (
        "configuration_reload_and_compatibility_warning"
    )
    UNHANDLED_EXCEPTION_WITH_SANITIZED_STACK_CONTEXT = (
        "unhandled_exception_with_sanitized_stack_context"
    )
    HEALTH_CHECK_FAILURE_AND_RECOVERY = "health_check_failure_and_recovery"


def can_sample_away_from_visibility(
    *, is_failure: bool, is_material_state_transition: bool
) -> bool:
    """SS13: "successful high-volume requests may be summarized or sampled, but failures and
    material state transitions remain visible.\""""
    return not (is_failure or is_material_state_transition)


@dataclass(frozen=True, slots=True)
class ConnectorLogFields:
    """SS14: "connector logs include" this literal field list."""

    package_version: str
    instance_version: str
    target_reference: str
    capability_id: str
    protocol_operation: str
    timeout_seconds: float
    attempt: int
    vendor_request_id: str | None
    parser_result: str
    normalized_failure_category: str | None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("package_version", self.package_version),
            ("instance_version", self.instance_version),
            ("target_reference", self.target_reference),
            ("capability_id", self.capability_id),
            ("protocol_operation", self.protocol_operation),
            ("parser_result", self.parser_result),
        ):
            if not value.strip():
                raise ValueError(f"connector log fields require {field_name}")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.attempt < 1:
            raise ValueError("attempt must be a positive, 1-based attempt number")


def target_timeout_is_logged_as_success() -> bool:
    """SS14: "a target timeout is not logged as success.\""""
    return False


def raw_vendor_payloads_are_enabled_by_default() -> bool:
    """SS14: "raw vendor payloads are disabled by default and require controlled diagnostic
    capture.\""""
    return False


class WorkflowLogEventKind(StrEnum):
    """SS15's eight required workflow/scheduler logging events."""

    DEFINITION_AND_RUN_VERSION = "definition_and_run_version"
    TRIGGER_AND_SCHEDULE_REFERENCE = "trigger_and_schedule_reference"
    CURRENT_STATE_TRANSITION_AND_REASON = "current_state_transition_and_reason"
    STEP_START_COMPLETION_RETRY_TIMEOUT_CANCELLATION_AND_COMPENSATION = (
        "step_start_completion_retry_timeout_cancellation_and_compensation"
    )
    INPUT_AND_OUTPUT_ARTIFACT_REFERENCES = "input_and_output_artifact_references"
    WAITING_CONDITION = "waiting_condition"
    OWNER_AND_DELEGATED_SERVICE_IDENTITY = "owner_and_delegated_service_identity"
    ORPHANED_STUCK_AND_OVERDUE_RUN_DETECTION = "orphaned_stuck_and_overdue_run_detection"


def workflow_can_be_logged_as_completed_when_final_result_unknown() -> bool:
    """SS15: "logs must not imply a workflow completed when a final verification or connector
    result is unknown.\""""
    return False


class AiLogSignalKind(StrEnum):
    """SS16's seven AI/RAG operational logging signal categories."""

    AGENT_ORCHESTRATOR_MODEL_ENDPOINT_AND_SAFE_MODEL_VERSION = (
        "agent_orchestrator_model_endpoint_and_safe_model_version"
    )
    REQUEST_CLASS_TOKEN_OR_CONTEXT_SIZE_LATENCY_TIMEOUT_AND_RETRY = (
        "request_class_token_or_context_size_latency_timeout_and_retry"
    )
    RETRIEVAL_COUNT_SOURCE_CLASS_RERANKING_AND_EMPTY_RESULT = (
        "retrieval_count_source_class_reranking_and_empty_result"
    )
    TOOL_SELECTION_AND_OUTCOME = "tool_selection_and_outcome"
    GUARDRAIL_POLICY_CITATION_GROUNDING_AND_STRUCTURED_OUTPUT_VALIDATION = (
        "guardrail_policy_citation_grounding_and_structured_output_validation"
    )
    REFUSAL_FALLBACK_DEGRADED_MODE_AND_HUMAN_REVIEW_ROUTING = (
        "refusal_fallback_degraded_mode_and_human_review_routing"
    )
    COST_OR_RESOURCE_USAGE = "cost_or_resource_usage"


def private_model_reasoning_is_logged() -> bool:
    """SS16: "private model reasoning is neither requested nor logged." A distinct question from
    AI Agents' `private_model_reasoning_is_stored` (ATLAS-040 SS22) -- this one is about the
    operational log stream, that one about durable audit retention."""
    return False


class SecurityLogSignalKind(StrEnum):
    """SS17's nine security logging detection-signal categories."""

    AUTHENTICATION_ABUSE_LOCKOUT_REPLAY_AND_PROVIDER_TRUST_FAILURE = (
        "authentication_abuse_lockout_replay_and_provider_trust_failure"
    )
    AUTHORIZATION_PROBING_AND_REPEATED_DENIAL = "authorization_probing_and_repeated_denial"
    SECRET_ACCESS_ANOMALY_AND_CREDENTIAL_VALIDATION_FAILURE = (
        "secret_access_anomaly_and_credential_validation_failure"
    )
    EXTENSION_INTEGRITY_OR_SIGNATURE_FAILURE = "extension_integrity_or_signature_failure"
    PROMPT_INJECTION_MALICIOUS_DOCUMENT_UNSAFE_TOOL_REQUEST_AND_GUARDRAIL_REJECTION = (
        "prompt_injection_malicious_document_unsafe_tool_request_and_guardrail_rejection"
    )
    AUDIT_PIPELINE_FAILURE_OR_INTEGRITY_ALERT = "audit_pipeline_failure_or_integrity_alert"
    UNEXPECTED_CROSS_SCOPE_ACCESS_ATTEMPT = "unexpected_cross_scope_access_attempt"
    EXCESSIVE_EXPORT_SEARCH_OR_ADMINISTRATIVE_ACTIVITY = (
        "excessive_export_search_or_administrative_activity"
    )
    CERTIFICATE_EXPIRY_AND_UNTRUSTED_COMMUNICATION = (
        "certificate_expiry_and_untrusted_communication"
    )
