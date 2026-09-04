"""ATLAS-047 SS24/SS25: safe failure matrix and platform-minimum exceptions.

SS24's table pairs each condition with a compound, sometimes multi-step required behavior (e.g.
"label limitation; propose safe check or stop"). `required_outcome_for` maps each condition to
the single most load-bearing `GuardrailOutcome` -- a defensible simplification stated plainly as
one, not a literal encoding of every row's full multi-part behavior.

`GuardrailException.__post_init__` gives SS25's "invariant guardrails have no customer override"
real teeth: an exception whose `rule_id` names one of the sixteen GRD invariants cannot be
constructed at all, the same structural guarantee `break_glass.py` uses in Policy Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.guardrails.domain.models import GuardrailInvariant, GuardrailOutcome
from atlas.modules.identity.domain.models import validate_stable_identifier

_INVARIANT_RULE_IDS = frozenset(invariant.value for invariant in GuardrailInvariant)


class SafeFailureCondition(StrEnum):
    """SS24's twelve named failure conditions."""

    IDENTITY_OR_AUTHORIZATION_UNCERTAIN = "identity_or_authorization_uncertain"
    POLICY_OR_GUARDRAIL_SERVICE_UNAVAILABLE = "policy_or_guardrail_service_unavailable"
    AUDIT_DURABILITY_UNAVAILABLE = "audit_durability_unavailable"
    TARGET_AMBIGUOUS_OR_SCOPE_MISMATCH = "target_ambiguous_or_scope_mismatch"
    EVIDENCE_INSUFFICIENT_OR_STALE = "evidence_insufficient_or_stale"
    PROMPT_INJECTION_SUSPECTED = "prompt_injection_suspected"
    SECRET_DETECTED = "secret_detected"
    MODEL_UNAVAILABLE_OR_INVALID_OUTPUT = "model_unavailable_or_invalid_output"
    TOOL_TIMEOUT_OR_PARTIAL_RESULT = "tool_timeout_or_partial_result"
    APPROVAL_EXPIRED_OR_MISMATCHED = "approval_expired_or_mismatched"
    GENERATED_ARTIFACT_UNAPPROVED = "generated_artifact_unapproved"
    CROSS_BOUNDARY_ACCESS_SIGNAL = "cross_boundary_access_signal"


_REQUIRED_OUTCOME: dict[SafeFailureCondition, GuardrailOutcome] = {
    SafeFailureCondition.IDENTITY_OR_AUTHORIZATION_UNCERTAIN: GuardrailOutcome.BLOCK,
    SafeFailureCondition.POLICY_OR_GUARDRAIL_SERVICE_UNAVAILABLE: GuardrailOutcome.BLOCK,
    SafeFailureCondition.AUDIT_DURABILITY_UNAVAILABLE: GuardrailOutcome.BLOCK,
    SafeFailureCondition.TARGET_AMBIGUOUS_OR_SCOPE_MISMATCH: GuardrailOutcome.BLOCK,
    SafeFailureCondition.EVIDENCE_INSUFFICIENT_OR_STALE: GuardrailOutcome.WARN,
    SafeFailureCondition.PROMPT_INJECTION_SUSPECTED: GuardrailOutcome.QUARANTINE,
    SafeFailureCondition.SECRET_DETECTED: GuardrailOutcome.REDACT,
    SafeFailureCondition.MODEL_UNAVAILABLE_OR_INVALID_OUTPUT: GuardrailOutcome.BLOCK,
    SafeFailureCondition.TOOL_TIMEOUT_OR_PARTIAL_RESULT: GuardrailOutcome.WARN,
    SafeFailureCondition.APPROVAL_EXPIRED_OR_MISMATCHED: GuardrailOutcome.BLOCK,
    SafeFailureCondition.GENERATED_ARTIFACT_UNAPPROVED: GuardrailOutcome.BLOCK,
    SafeFailureCondition.CROSS_BOUNDARY_ACCESS_SIGNAL: GuardrailOutcome.BLOCK,
}


def required_outcome_for(condition: SafeFailureCondition) -> GuardrailOutcome:
    return _REQUIRED_OUTCOME[condition]


@dataclass(frozen=True, slots=True)
class GuardrailException:
    """SS25: a platform-minimum exception. Every field SS25 requires is a real field, not a
    free-text justification blob one of them could hide inside."""

    exception_id: str
    rule_id: str
    requested_change: str
    business_justification: str
    technical_justification: str
    risk_description: str
    compensating_controls: tuple[str, ...]
    requester_identity_id: str
    security_reviewer_identity_id: str
    approver_identity_id: str
    target_id: str
    environment_id: str
    starts_at: datetime
    expires_at: datetime
    automatic_rollback: bool
    monitoring_plan: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.exception_id, "exception_id")
        if not self.rule_id.strip():
            raise ValueError("a guardrail exception requires a rule_id")
        if self.rule_id in _INVARIANT_RULE_IDS:
            raise ValueError(
                'an exception cannot target a non-overridable invariant (SS25: "invariant'
                ' guardrails have no customer override")'
            )
        if not self.requested_change.strip():
            raise ValueError("a guardrail exception requires a requested change")
        if not self.business_justification.strip():
            raise ValueError("a guardrail exception requires a business justification")
        if not self.technical_justification.strip():
            raise ValueError("a guardrail exception requires a technical justification")
        if not self.risk_description.strip():
            raise ValueError("a guardrail exception requires a risk description")
        if not self.compensating_controls:
            raise ValueError("a guardrail exception requires at least one compensating control")
        validate_stable_identifier(self.requester_identity_id, "requester_identity_id")
        validate_stable_identifier(
            self.security_reviewer_identity_id, "security_reviewer_identity_id"
        )
        validate_stable_identifier(self.approver_identity_id, "approver_identity_id")
        if self.requester_identity_id == self.approver_identity_id:
            raise ValueError("the requester and approver must be different identities")
        validate_stable_identifier(self.target_id, "target_id")
        validate_stable_identifier(self.environment_id, "environment_id")
        if self.starts_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("starts_at and expires_at must be timezone-aware")
        if self.expires_at <= self.starts_at:
            raise ValueError("expires_at must be later than starts_at")
        if not self.automatic_rollback:
            raise ValueError(
                'a guardrail exception requires automatic rollback (SS25: "start, expiry, and'
                ' automatic rollback")'
            )
        if not self.monitoring_plan.strip():
            raise ValueError("a guardrail exception requires a monitoring plan")

    def is_active_at(self, at: datetime) -> bool:
        return self.starts_at <= at < self.expires_at
