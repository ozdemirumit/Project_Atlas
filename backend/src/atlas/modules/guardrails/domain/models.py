"""ATLAS-047 SS7/SS8/SS26: guardrail classes, the sixteen non-overridable invariants, and the
guardrail decision contract.

This is the first Guardrails slice: the registry and decision shape every later layer (input,
retrieval, reasoning, tool-use, output, ...) will produce decisions against. No enforcement logic
lives here yet -- just the vocabulary those layers share.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class GuardrailClass(StrEnum):
    """SS7's four configuration postures. The class is explicit for every rule -- an advisory
    detector cannot be presented as deterministic enforcement."""

    INVARIANT = "invariant"
    PLATFORM_MINIMUM = "platform_minimum"
    POLICY_CONFIGURABLE = "policy_configurable"
    ADVISORY = "advisory"


class GuardrailInvariant(StrEnum):
    """SS8's sixteen non-overridable invariants, using the document's own GRD-NNN identifiers as
    the enum values so a decision's rule_id can reference one directly and traceably. SS25: "an
    emergency process cannot disable GRD-001 through GRD-016" -- no exception process this
    codebase builds may ever target one of these for weakening or removal."""

    GRD_001_NO_INDEPENDENT_AUTHORITY = "GRD-001"
    GRD_002_NO_UNRESTRICTED_CREDENTIALS = "GRD-002"
    GRD_003_GOVERNED_TOOLS_ONLY = "GRD-003"
    GRD_004_AUTHORITY_CANNOT_EXPAND = "GRD-004"
    GRD_005_READ_ONLY_BY_DEFAULT = "GRD-005"
    GRD_006_EVIDENCE_AND_UNCERTAINTY_MANDATORY = "GRD-006"
    GRD_007_IMPACT_AND_RECOVERY_PRECEDE_APPROVAL = "GRD-007"
    GRD_008_APPROVAL_IS_EXACT_AND_HUMAN = "GRD-008"
    GRD_009_AUDIT_CANNOT_BE_BYPASSED = "GRD-009"
    GRD_010_SECRETS_NEVER_ENTER_UNSAFE_CHANNELS = "GRD-010"
    GRD_011_ORGANIZATIONAL_BOUNDARIES_PRESERVED = "GRD-011"
    GRD_012_GENERATED_ARTIFACTS_ARE_UNTRUSTED = "GRD-012"
    GRD_013_UNKNOWN_IS_NOT_SUCCESS = "GRD-013"
    GRD_014_CONTROL_FAILURE_STOPS_UNSAFE_PROGRESS = "GRD-014"
    GRD_015_MODEL_CANNOT_OVERRIDE_DETERMINISTIC_CONTROLS = "GRD-015"
    GRD_016_HUMANS_RETAIN_MEANINGFUL_CONTROL = "GRD-016"


GUARDRAIL_INVARIANT_SUMMARIES: dict[GuardrailInvariant, str] = {
    GuardrailInvariant.GRD_001_NO_INDEPENDENT_AUTHORITY: (
        "AI can analyze, retrieve, calculate, explain, recommend, and draft. It cannot"
        " independently authorize or execute infrastructure-changing activity."
    ),
    GuardrailInvariant.GRD_002_NO_UNRESTRICTED_CREDENTIALS: (
        "Secret values, private keys, unrestricted tokens, and reusable vendor credentials are"
        " prohibited in model context."
    ),
    GuardrailInvariant.GRD_003_GOVERNED_TOOLS_ONLY: (
        "Live infrastructure access must use registered, typed, scoped, versioned MCP or"
        " platform capabilities."
    ),
    GuardrailInvariant.GRD_004_AUTHORITY_CANNOT_EXPAND: (
        "Effective authority is the intersection of every applicable control; delegation,"
        " handoff, or approval cannot broaden it."
    ),
    GuardrailInvariant.GRD_005_READ_ONLY_BY_DEFAULT: (
        "Unknown, new, generated, or unclassified capabilities are denied and treated as"
        " write-capable until reviewed."
    ),
    GuardrailInvariant.GRD_006_EVIDENCE_AND_UNCERTAINTY_MANDATORY: (
        "Material findings and recommendations require evidence, provenance, freshness,"
        " assumptions, unknowns, alternatives, and confidence rationale."
    ),
    GuardrailInvariant.GRD_007_IMPACT_AND_RECOVERY_PRECEDE_APPROVAL: (
        "Target, blast radius, risk, interruption, duration, preconditions, verification, and"
        " recovery must be present or explicitly block readiness."
    ),
    GuardrailInvariant.GRD_008_APPROVAL_IS_EXACT_AND_HUMAN: (
        "Only eligible authenticated humans can approve, and approval binds to one exact"
        " immutable proposal."
    ),
    GuardrailInvariant.GRD_009_AUDIT_CANNOT_BE_BYPASSED: (
        "Required security, AI, tool, policy, approval, and operational events must be durably"
        " audited; consequential progress stops when required audit durability is unavailable."
    ),
    GuardrailInvariant.GRD_010_SECRETS_NEVER_ENTER_UNSAFE_CHANNELS: (
        "Secrets are excluded from prompts, model output, logs, audit payloads, reports,"
        " generated artifacts, support bundles, and unapproved external destinations."
    ),
    GuardrailInvariant.GRD_011_ORGANIZATIONAL_BOUNDARIES_PRESERVED: (
        "No user, agent, tool, retrieval, cache, metric, error, or export may reveal data"
        " outside authorized organization, environment, purpose, and classification."
    ),
    GuardrailInvariant.GRD_012_GENERATED_ARTIFACTS_ARE_UNTRUSTED: (
        "Generated code, connectors, policies, workflows, queries, runbooks, mappings, and rules"
        " require isolated validation, security review, testing, signing, and human approval"
        " before production use."
    ),
    GuardrailInvariant.GRD_013_UNKNOWN_IS_NOT_SUCCESS: (
        "Timeout, partial completion, stale state, ambiguous target, conflicting evidence, or"
        " unavailable verification cannot be reported as success or safe."
    ),
    GuardrailInvariant.GRD_014_CONTROL_FAILURE_STOPS_UNSAFE_PROGRESS: (
        "Failure of identity, authorization, policy, approval, guardrail, target validation,"
        " connector trust, or audit blocks the affected protected operation."
    ),
    GuardrailInvariant.GRD_015_MODEL_CANNOT_OVERRIDE_DETERMINISTIC_CONTROLS: (
        "The model cannot reinterpret denial, alter policy, forge approval, change capability"
        " class, validate its own generated artifact, or mark an operation successful."
    ),
    GuardrailInvariant.GRD_016_HUMANS_RETAIN_MEANINGFUL_CONTROL: (
        "Users can review evidence, challenge conclusions, cancel eligible work, reject"
        " recommendations, request more evidence, and understand what a decision permits."
    ),
}


class GuardrailOutcome(StrEnum):
    """SS26's six outcomes."""

    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"
    QUARANTINE = "quarantine"
    REDACT = "redact"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class GuardrailDecision:
    """SS26's exact decision contract. "Model-generated prose cannot alter the structured
    decision" (SS26) -- every field here is a typed value or a stable code, never free text the
    model itself produced."""

    decision_id: str
    decided_at: datetime
    rule_id: str
    rule_version: int
    guardrail_class: GuardrailClass
    input_reference: str
    outcome: GuardrailOutcome
    reason_code: str
    detail: str
    evidence_references: tuple[str, ...]
    detector_version: str
    required_next_action: str
    correlation_id: str
    re_evaluation_condition: str | None = None
    expires_at: datetime | None = None
    audit_reference: str | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.decision_id, "decision_id")
        validate_stable_identifier(self.rule_id, "rule_id")
        validate_stable_identifier(self.correlation_id, "correlation_id")
        if self.rule_version < 1:
            raise ValueError("rule_version must be positive")
        if self.decided_at.tzinfo is None:
            raise ValueError("decided_at must be timezone-aware")
        if not self.input_reference.strip():
            raise ValueError("a guardrail decision requires an input reference")
        if not self.reason_code.strip():
            raise ValueError("a guardrail decision requires a reason code")
        if not self.detail.strip():
            raise ValueError("a guardrail decision requires authorized detail")
        if not self.detector_version.strip():
            raise ValueError("a guardrail decision requires a detector version")
        if not self.required_next_action.strip():
            raise ValueError("a guardrail decision requires a required next action")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        if self.guardrail_class is GuardrailClass.INVARIANT and self.outcome not in (
            GuardrailOutcome.PASS,
            GuardrailOutcome.BLOCK,
        ):
            raise ValueError(
                'an invariant guardrail decision can only pass or block (SS7: "must always'
                ' hold; violation stops operation")'
            )

    @property
    def blocking(self) -> bool:
        return self.outcome in (GuardrailOutcome.BLOCK, GuardrailOutcome.QUARANTINE)
