"""ATLAS-040 SS16: output validation.

Mirrors `change_impact.domain.validation_freshness.ValidationCheck`'s shape (this session's
established pattern for turning a prose checklist into named, individually pass/fail items).
`OutputValidationResult.__post_init__` gives "repeated repair is bounded" a real, checked
invariant -- construction itself fails once `repair_attempt_count` exceeds `max_repair_attempts`
-- and refuses `ACCEPT` while any check has failed, rather than leaving that consistency to
convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class OutputValidationCheckKind(StrEnum):
    """SS16's nine validation checks."""

    SCHEMA_AND_ENUM_VALIDATION = "schema_and_enum_validation"
    CITATION_EXISTENCE_ACCESS_AND_CLAIM_SUPPORT = "citation_existence_access_and_claim_support"
    TARGET_AND_IDENTIFIER_VALIDATION = "target_and_identifier_validation"
    UNSUPPORTED_CERTAINTY_AND_CONTRADICTION_CHECKS = (
        "unsupported_certainty_and_contradiction_checks"
    )
    REQUIRED_RISK_IMPACT_RECOVERY_AND_UNKNOWN_SECTIONS = (
        "required_risk_impact_recovery_and_unknown_sections"
    )
    SECRET_AND_SENSITIVE_DATA_SCANNING = "secret_and_sensitive_data_scanning"
    POLICY_AND_GUARDRAIL_CLASSIFICATION = "policy_and_guardrail_classification"
    TOOL_CALL_RESULT_AND_ARTIFACT_REFERENCE_VALIDATION = (
        "tool_call_result_and_artifact_reference_validation"
    )
    SIZE_AND_RENDERING_SAFETY = "size_and_rendering_safety"


@dataclass(frozen=True, slots=True)
class OutputValidationCheck:
    kind: OutputValidationCheckKind
    passed: bool
    detail: str

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("an output validation check requires a detail")


class ValidationDisposition(StrEnum):
    """SS16: "validation can reject, redact, downgrade, request repair, or route to human
    review.\""""

    ACCEPT = "accept"
    REJECT = "reject"
    REDACT = "redact"
    DOWNGRADE = "downgrade"
    REQUEST_REPAIR = "request_repair"
    ROUTE_TO_HUMAN_REVIEW = "route_to_human_review"


@dataclass(frozen=True, slots=True)
class OutputValidationResult:
    envelope_id: str
    checks: tuple[OutputValidationCheck, ...]
    disposition: ValidationDisposition
    repair_attempt_count: int
    max_repair_attempts: int

    def __post_init__(self) -> None:
        validate_stable_identifier(self.envelope_id, "envelope_id")
        if not self.checks:
            raise ValueError("an output validation result requires at least one check")
        kinds = [check.kind for check in self.checks]
        if len(set(kinds)) != len(kinds):
            raise ValueError("an output validation result must not repeat a check kind")
        if self.repair_attempt_count < 0:
            raise ValueError("repair_attempt_count must not be negative")
        if self.max_repair_attempts < 0:
            raise ValueError("max_repair_attempts must not be negative")
        if self.repair_attempt_count > self.max_repair_attempts:
            raise ValueError(
                "repair_attempt_count exceeds max_repair_attempts -- repeated repair is bounded"
            )
        if self.disposition is ValidationDisposition.ACCEPT and not all(
            check.passed for check in self.checks
        ):
            raise ValueError("disposition cannot be ACCEPT while a check has failed")

    @property
    def all_checks_passed(self) -> bool:
        return all(check.passed for check in self.checks)
