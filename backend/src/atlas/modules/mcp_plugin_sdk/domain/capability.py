"""ATLAS-021 SS13/SS14: the capability definition API and handler contract.

`CapabilityDefinition` wraps `connectors.domain.models.CapabilityManifest` directly for SS13's
stable-identifier/version/description/target-types/C0-C5-class/side-effect/timeout/idempotency
elements, adding only what that runtime type does not carry (input/output schemas, permission
declarations, cancellation behavior, concurrency/rate-limit hints, preconditions, result evidence
requirements, error mapping, test scenarios). `HandlerComplianceReport` mirrors the
`ValidationCheck`/`OutputValidationCheck` pattern established in Change Impact and AI Agents for
turning SS14's eight prose handler rules into named, individually checkable items.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.connectors.domain.models import CapabilityManifest
from atlas.modules.identity.domain.models import validate_stable_identifier


class CancellationBehavior(StrEnum):
    """SS13: "cancellation behavior.\""""

    IMMEDIATE = "immediate"
    COOPERATIVE_CHECKPOINTED = "cooperative_checkpointed"
    NOT_CANCELLABLE = "not_cancellable"


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    manifest: CapabilityManifest
    input_schema_id: str
    output_schema_id: str
    permission_declarations: tuple[str, ...]
    cancellation_behavior: CancellationBehavior
    max_concurrency: int
    rate_limit_per_minute: int | None
    preconditions: tuple[str, ...]
    required_result_evidence_fields: tuple[str, ...]
    error_mapping_ids: tuple[str, ...]
    test_scenario_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.input_schema_id, "input_schema_id")
        validate_stable_identifier(self.output_schema_id, "output_schema_id")
        if not self.permission_declarations:
            raise ValueError("a capability definition requires permission declarations")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        if self.rate_limit_per_minute is not None and self.rate_limit_per_minute < 1:
            raise ValueError("rate_limit_per_minute must be positive")
        if not self.required_result_evidence_fields:
            raise ValueError("a capability definition requires result evidence fields")
        if not self.test_scenario_ids:
            raise ValueError("a capability definition requires test scenarios")


def is_consistent_with_manifest(
    definition: CapabilityDefinition, *, manifest_capability_ids: frozenset[str]
) -> bool:
    """SS13: "SDK registration compares declarations to the package manifest and fails on
    inconsistency.\""""
    return definition.manifest.capability_id in manifest_capability_ids


class HandlerRule(StrEnum):
    """SS14's eight handler rules."""

    VALIDATES_VENDOR_CONSTRAINTS_BEFORE_REMOTE_CALLS = (
        "validates_vendor_constraints_before_remote_calls"
    )
    CHECKS_CANCELLATION_BEFORE_AND_BETWEEN_BOUNDED_OPERATIONS = (
        "checks_cancellation_before_and_between_bounded_operations"
    )
    USES_CONTEXT_DEADLINE_NOT_UNBOUNDED_TIMEOUT = "uses_context_deadline_not_unbounded_timeout"
    RETURNS_STRUCTURED_OUTCOMES_NOT_PRINTED_TEXT = "returns_structured_outcomes_not_printed_text"
    PRESERVES_SOURCE_OBSERVATION_TIME_AND_VENDOR_VERSION = (
        "preserves_source_observation_time_and_vendor_version"
    )
    MAPS_VENDOR_ERRORS_WITHOUT_LEAKING_CREDENTIALS_OR_PAYLOADS = (
        "maps_vendor_errors_without_leaking_credentials_or_payloads"
    )
    NEVER_CREATES_NESTED_SHELL_FOR_CLI_OPERATIONS = "never_creates_nested_shell_for_cli_operations"
    NEVER_CALLS_LLM_OR_POLICY_ENGINE_DIRECTLY = "never_calls_llm_or_policy_engine_directly"


@dataclass(frozen=True, slots=True)
class HandlerComplianceCheck:
    rule: HandlerRule
    passed: bool
    detail: str

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("a handler compliance check requires a detail")


@dataclass(frozen=True, slots=True)
class HandlerComplianceReport:
    capability_id: str
    checks: tuple[HandlerComplianceCheck, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.capability_id, "capability_id")
        rules = [check.rule for check in self.checks]
        if len(set(rules)) != len(rules):
            raise ValueError("a handler compliance report must not repeat a rule")
        if set(rules) != set(HandlerRule):
            raise ValueError("a handler compliance report requires every handler rule")

    @property
    def all_rules_satisfied(self) -> bool:
        return all(check.passed for check in self.checks)
