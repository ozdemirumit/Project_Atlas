"""ATLAS-040 SS11/SS12: tool access and effective authority.

`effective_authority_grants_access` renders SS12's "intersection of" eight elements literally: an
`all()` over eight independent grant flags, matching "if any required element is missing or denies
access, the call is denied" exactly -- one `False` anywhere denies the whole call, with no path to
partial or default access.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import validate_stable_identifier


class ProhibitedToolKind(StrEnum):
    """SS11: "arbitrary shell, unrestricted HTTP, dynamic code execution, and raw credential
    access are prohibited production tools.\""""

    ARBITRARY_SHELL = "arbitrary_shell"
    UNRESTRICTED_HTTP = "unrestricted_http"
    DYNAMIC_CODE_EXECUTION = "dynamic_code_execution"
    RAW_CREDENTIAL_ACCESS = "raw_credential_access"


def is_available_to_agents(capability_class: CapabilityClass) -> bool:
    """SS11: C0-C2 are available to agents (C2 with extra gating below); "C3 through C5 are not
    directly available to AI agents.\""""
    return capability_class in (
        CapabilityClass.C0_INFORMATIONAL,
        CapabilityClass.C1_READ_ONLY,
        CapabilityClass.C2_DIAGNOSTIC,
    )


def is_normal_agent_access_baseline(capability_class: CapabilityClass) -> bool:
    """SS11: "C0 and C1 are the normal agent-access baseline.\""""
    return capability_class in (CapabilityClass.C0_INFORMATIONAL, CapabilityClass.C1_READ_ONLY)


def requires_explicit_design_and_possible_approval(capability_class: CapabilityClass) -> bool:
    """SS11: "C2 calls require explicit product and policy design and may require human
    approval.\""""
    return capability_class is CapabilityClass.C2_DIAGNOSTIC


@dataclass(frozen=True, slots=True)
class ToolCallRequest:
    """SS11: "every tool call uses typed parameters, target scope, timeout, idempotency where
    applicable, and a correlation ID.\""""

    tool_id: str
    agent_id: str
    task_id: str
    typed_parameters: tuple[tuple[str, str], ...]
    target_scope: tuple[str, ...]
    timeout_seconds: float
    idempotency_key: str | None
    correlation_id: str
    capability_class: CapabilityClass

    def __post_init__(self) -> None:
        validate_stable_identifier(self.tool_id, "tool_id")
        validate_stable_identifier(self.agent_id, "agent_id")
        validate_stable_identifier(self.task_id, "task_id")
        if not self.target_scope:
            raise ValueError("a tool call requires a target scope")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not self.correlation_id.strip():
            raise ValueError("a tool call requires a correlation id")


@dataclass(frozen=True, slots=True)
class EffectiveAuthorityInputs:
    """SS12's eight intersected elements, each reduced to whether it grants this specific call."""

    authenticated_user_scope_grants: bool
    service_identity_permission_grants: bool
    agent_definition_allowlist_grants: bool
    task_contract_grants: bool
    workflow_constraint_grants: bool
    policy_and_guardrail_grants: bool
    tool_and_connector_capability_grants: bool
    current_environment_state_grants: bool


def effective_authority_grants_access(inputs: EffectiveAuthorityInputs) -> bool:
    """SS12: "an agent's effective access is the intersection of" eight elements. "If any
    required element is missing or denies access, the call is denied.\""""
    return all(
        (
            inputs.authenticated_user_scope_grants,
            inputs.service_identity_permission_grants,
            inputs.agent_definition_allowlist_grants,
            inputs.task_contract_grants,
            inputs.workflow_constraint_grants,
            inputs.policy_and_guardrail_grants,
            inputs.tool_and_connector_capability_grants,
            inputs.current_environment_state_grants,
        )
    )


def approval_can_expand_effective_authority() -> bool:
    """SS12: "approval cannot expand this intersection.\""""
    return False


def tool_output_is_trusted() -> bool:
    """SS11: "tool output is untrusted, size-bounded, classified, normalized, and protected
    against prompt injection.\""""
    return False


@dataclass(frozen=True, slots=True)
class ToolOutputEnvelope:
    tool_id: str
    raw_size_bytes: int
    size_bound_bytes: int
    classification: DataClassification
    normalized: bool
    prompt_injection_scan_passed: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.tool_id, "tool_id")
        if self.raw_size_bytes < 0:
            raise ValueError("raw_size_bytes must not be negative")
        if self.size_bound_bytes < 1:
            raise ValueError("size_bound_bytes must be positive")
        if self.raw_size_bytes > self.size_bound_bytes:
            raise ValueError("tool output exceeds its size bound")
