"""ATLAS-021 SS16/SS17: the result model and error model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier


class CapabilityOutcomeState(StrEnum):
    """SS16: "outcome state.\""""

    SUCCESS = "success"
    PARTIAL = "partial"
    UNCERTAIN = "uncertain"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    """SS16's declared elements. "Result builders prevent a success outcome without required
    success evidence" is a construction-time guarantee: a `SUCCESS` result cannot be built with
    no evidence references."""

    outcome_state: CapabilityOutcomeState
    capability_specific_data: tuple[tuple[str, str], ...]
    target_id: str
    observed_at: datetime
    evidence_references: tuple[str, ...]
    source_references: tuple[str, ...]
    warnings: tuple[str, ...]
    omissions: tuple[str, ...]
    freshness_seconds: float
    side_effect_confirmation: str | None
    sanitized_vendor_diagnostic_reference: str | None
    retry_guidance: str | None
    next_step_guidance: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.target_id, "target_id")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.freshness_seconds < 0:
            raise ValueError("freshness_seconds must not be negative")
        if self.outcome_state is CapabilityOutcomeState.SUCCESS and not self.evidence_references:
            raise ValueError(
                "SS16: result builders prevent a success outcome without required success evidence"
            )


class ConnectorErrorCode(StrEnum):
    """SS17's thirteen error classes, mapped to the ATLAS-020 taxonomy."""

    INVALID_INPUT = "invalid_input"
    AUTHENTICATION_FAILURE = "authentication_failure"
    PERMISSION_FAILURE = "permission_failure"
    TARGET_UNAVAILABLE = "target_unavailable"
    INCOMPATIBLE_TARGET = "incompatible_target"
    RATE_LIMITED = "rate_limited"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    MALFORMED_RESPONSE = "malformed_response"
    PARTIAL_RESULT = "partial_result"
    OUTCOME_UNCERTAIN = "outcome_uncertain"
    CONNECTOR_INTERNAL_FAILURE = "connector_internal_failure"
    SECURITY_VIOLATION = "security_violation"


def raw_exception_is_a_public_result() -> bool:
    """SS17: "raw exceptions are not public results.\""""
    return False


@dataclass(frozen=True, slots=True)
class ConnectorError:
    """SS17: "errors include stable code, safe summary, retryability, vendor reference, and
    optional diagnostic evidence." Reuses Guardrails' `detect_secret_patterns` on the summary --
    a "safe" summary that matches a secret pattern is not actually safe."""

    code: ConnectorErrorCode
    safe_summary: str
    retryable: bool
    vendor_reference: str | None
    diagnostic_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.safe_summary.strip():
            raise ValueError("a connector error requires a safe summary")
        if detect_secret_patterns(self.safe_summary):
            raise ValueError(
                "SS17: raw exceptions are not public results -- a safe summary must not "
                "contain secret-looking content"
            )
