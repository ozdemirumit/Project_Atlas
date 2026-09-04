"""ATLAS-040 SS20/SS21: prompt/model lifecycle and security.

"Customer instructions cannot override platform system rules" (SS20) and "tool results and
retrieved documents are treated as untrusted data, not higher-priority instructions" (SS21) are
both already `guardrails.domain.instruction_hierarchy.InstructionSource`/`can_override` (ATLAS-047)
-- the same reuse this session has now established across Runbook Engine, Reasoning, Decision
Engine, and Change Impact, needing no new code here. "Context and artifact access preserve
organization and classification boundaries" is already `context.ContextItem`'s own
`classification`/`authorized_principals` (slice 7). "Model endpoint telemetry follows configured
data-boundary policy" is a platform data-boundary configuration concern, not a per-object
invariant this module's types can enforce -- genuinely out of scope here, the same honest
carve-out Change Impact's SS28 slice made for the identically-worded requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class TemplateKind(StrEnum):
    """SS20: "system, role, tool, and response templates are versioned separately.\""""

    SYSTEM = "system"
    ROLE = "role"
    TOOL = "tool"
    RESPONSE = "response"


@dataclass(frozen=True, slots=True)
class PromptTemplateVersion:
    """`reviewed_as_behavior_change` must be `True` to construct at all -- SS20: "prompt changes
    are reviewed as behavior changes" is not optional guidance here."""

    template_id: str
    kind: TemplateKind
    version: int
    reviewed_as_behavior_change: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.template_id, "template_id")
        if self.version < 1:
            raise ValueError("a prompt template version requires a positive version")
        if not self.reviewed_as_behavior_change:
            raise ValueError("SS20: prompt changes are reviewed as behavior changes")


class ModelUpgradeEvaluationDimension(StrEnum):
    """SS20: "model upgrades require compatibility, safety, quality, latency, and resource
    evaluation.\""""

    COMPATIBILITY = "compatibility"
    SAFETY = "safety"
    QUALITY = "quality"
    LATENCY = "latency"
    RESOURCE = "resource"


@dataclass(frozen=True, slots=True)
class ModelUpgradeEvaluation:
    from_model_id: str
    to_model_id: str
    dimension_results: tuple[tuple[ModelUpgradeEvaluationDimension, bool], ...]

    def __post_init__(self) -> None:
        if not self.from_model_id.strip():
            raise ValueError("a model upgrade evaluation requires a source model id")
        if not self.to_model_id.strip():
            raise ValueError("a model upgrade evaluation requires a target model id")
        evaluated_dimensions = {dimension for dimension, _ in self.dimension_results}
        if evaluated_dimensions != set(ModelUpgradeEvaluationDimension):
            raise ValueError("a model upgrade evaluation requires every evaluation dimension")

    @property
    def passed(self) -> bool:
        return all(passed for _, passed in self.dimension_results)


@dataclass(frozen=True, slots=True)
class ProductionRunReference:
    """SS20: "production runs retain model and prompt references.\""""

    run_id: str
    model_id: str
    model_version: str
    prompt_template_references: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.run_id, "run_id")
        validate_stable_identifier(self.model_id, "model_id")
        if not self.model_version.strip():
            raise ValueError("a production run reference requires a model version")
        if not self.prompt_template_references:
            raise ValueError("a production run reference requires prompt template references")


@dataclass(frozen=True, slots=True)
class RollbackTarget:
    """`is_validated_compatible` must be `True` to construct at all -- SS20: "rollback restores a
    validated compatible combination.\""""

    combination_id: str
    is_validated_compatible: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.combination_id, "combination_id")
        if not self.is_validated_compatible:
            raise ValueError("SS20: rollback restores a validated compatible combination")


def agents_run_with_infrastructure_credentials() -> bool:
    """SS21: "agents run without infrastructure credentials.\""""
    return False


def security_review_agent_output_replaces_deterministic_enforcement() -> bool:
    """SS21: "Security Review Agent output supplements but never replaces deterministic
    enforcement.\""""
    return False


@dataclass(frozen=True, slots=True)
class NetworkDestinationAllowlist:
    """SS21: "network destinations are allowlisted through platform tools.\""""

    allowed_hosts: frozenset[str]

    def __post_init__(self) -> None:
        if not self.allowed_hosts:
            raise ValueError("a network destination allowlist requires at least one host")

    def is_allowed(self, host: str) -> bool:
        return host in self.allowed_hosts


@dataclass(frozen=True, slots=True)
class IsolatedGenerationEnvironment:
    """`has_production_secrets` must be `False` to construct at all -- SS21: "code or connector
    generation occurs in isolated environments with no production secrets.\""""

    environment_id: str
    has_production_secrets: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.environment_id, "environment_id")
        if self.has_production_secrets:
            raise ValueError(
                "SS21: code or connector generation environments carry no production secrets"
            )
