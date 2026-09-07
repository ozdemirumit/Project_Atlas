"""ATLAS-033 SS10/SS11/SS12: correlation and causality (the pieces `core.structured_logging.
LogCorrelation` doesn't cover), content rules, and redaction/data minimization.

`scan_for_secret_content` reuses Guardrails' `detect_secret_patterns` -- the reason this module
exists separately from `atlas.core.structured_logging` at all, since `atlas.core` cannot depend on
`atlas.modules.guardrails` without inverting the platform's dependency direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class CausalityLink:
    """SS10: "cross-service messages preserve causality through parent-event or trace
    context.\""""

    parent_event_id: str | None
    trace_context: str | None

    def __post_init__(self) -> None:
        if self.parent_event_id is None and self.trace_context is None:
            raise ValueError("a causality link requires a parent event id or trace context")


@dataclass(frozen=True, slots=True)
class ScheduledWorkAttribution:
    """SS10: "scheduled work records the schedule and accountable owner.\""""

    schedule_reference: str
    accountable_owner: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.schedule_reference, "schedule_reference")
        if not self.accountable_owner.strip():
            raise ValueError("a scheduled work attribution requires an accountable owner")


class ProhibitedLogContentKind(StrEnum):
    """SS11's seven prohibited content kinds."""

    PASSWORDS_TOKENS_KEYS_SECRETS_OR_AUTH_HEADERS = "passwords_tokens_keys_secrets_or_auth_headers"
    FULL_CONNECTOR_COMMANDS_WITH_SENSITIVE_ARGUMENTS = (
        "full_connector_commands_with_sensitive_arguments"
    )
    RAW_DOCUMENTS_PROMPTS_MODEL_RESPONSES_OR_RETRIEVED_CHUNKS = (
        "raw_documents_prompts_model_responses_or_retrieved_chunks"
    )
    UNBOUNDED_REQUEST_OR_RESPONSE_BODIES = "unbounded_request_or_response_bodies"
    PERSONAL_OR_INFRASTRUCTURE_DATA_NOT_NEEDED_FOR_OPERATIONS = (
        "personal_or_infrastructure_data_not_needed_for_operations"
    )
    DECRYPTED_CREDENTIALS_OR_SECRET_MANAGER_RESPONSES = (
        "decrypted_credentials_or_secret_manager_responses"
    )
    STACK_TRACES_EXPOSED_TO_UNPRIVILEGED_USERS = "stack_traces_exposed_to_unprivileged_users"


def scan_for_secret_content(text: str) -> bool:
    """SS11: covers the pattern-detectable prohibited content kinds (passwords/tokens/keys/
    secrets/auth headers; decrypted credentials). The other five kinds (full commands, raw
    documents/prompts, unbounded bodies, personal/infrastructure data, unprivileged stack traces)
    are structural field-shaping decisions a pattern scan cannot detect -- those are enforced by
    which fields a log record type exposes in the first place, not by scanning content."""
    return bool(detect_secret_patterns(text))


@dataclass(frozen=True, slots=True)
class SensitiveArtifactReference:
    """SS11: "sensitive artifacts are stored in governed evidence stores and referenced by
    opaque identifiers." Reference-only, extending this session's established pattern -- no field
    here could carry the sensitive artifact's own content."""

    evidence_store_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_store_reference, "evidence_store_reference")


class RedactionStage(StrEnum):
    """SS12: "redaction occurs as close to the producer as possible and again at centralized
    ingestion.\""""

    PRODUCER = "producer"
    CENTRALIZED_INGESTION = "centralized_ingestion"


@dataclass(frozen=True, slots=True)
class RedactionRule:
    """SS12: "versioned rules cover known secret names, headers, URI parameters, structured
    fields, and vendor patterns.\""""

    rule_id: str
    version: int
    covers: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.rule_id, "rule_id")
        if self.version < 1:
            raise ValueError("a redaction rule requires a positive version")
        if not self.covers.strip():
            raise ValueError("a redaction rule requires a description of what it covers")


@dataclass(frozen=True, slots=True)
class RedactionOutcome:
    """SS12: "operators can see that content was removed and which policy version applied.\""""

    field_name: str
    rule_version_applied: int
    was_redacted: bool

    def __post_init__(self) -> None:
        if not self.field_name.strip():
            raise ValueError("a redaction outcome requires a field name")
        if self.rule_version_applied < 1:
            raise ValueError("a redaction outcome requires a positive rule version")


def debug_mode_can_disable_mandatory_redaction() -> bool:
    """SS12: "debug mode cannot disable mandatory redaction.\""""
    return False


@dataclass(frozen=True, slots=True)
class RedactionFailure:
    """SS12: "redaction failures create alerts and can quarantine affected records.\""""

    record_reference: str
    reason: str
    quarantined: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.record_reference, "record_reference")
        if not self.reason.strip():
            raise ValueError("a redaction failure requires a reason")
