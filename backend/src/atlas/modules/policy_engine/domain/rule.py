"""ATLAS-025 rule content.

SS2 explicitly puts "final policy language or engine technology" out of scope, and SS30 lists
"which policy language and engine are selected" as an open ADR question -- the document
deliberately does not choose one. This module makes that choice for the platform: a small,
closed, attribute-based rule format (compare one named, controlled field on a decision request
against one or more literal values) rather than a general expression language. This keeps
evaluation genuinely deterministic and isolated from LLM output (SS23) without building an
arbitrary code-execution engine. `PolicyConditionField` is deliberately closed -- it only
references fields `PolicyDecisionRequest` (SS7-derived) already defines; extending the evaluable
vocabulary means extending that request type first, in its own reviewed slice.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.policy_engine.domain.models import PolicyDecisionOutcome, PolicyDecisionRequest


class PolicyConditionField(StrEnum):
    OPERATION_ID = "operation_id"
    CAPABILITY_CLASS = "capability_class"
    ACTOR_ORGANIZATION_ID = "actor_organization_id"
    ACTOR_ENVIRONMENT_ID = "actor_environment_id"
    TARGET_ORGANIZATION_ID = "target_organization_id"
    TARGET_ENVIRONMENT_ID = "target_environment_id"
    ACTOR_IS_AI = "actor_is_ai"
    CONNECTOR_TRUST = "connector_trust"
    APPROVAL_STATUS = "approval_status"


class PolicyConditionOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"


def _field_value(request: PolicyDecisionRequest, field: PolicyConditionField) -> str:
    if field is PolicyConditionField.OPERATION_ID:
        return request.operation_id
    if field is PolicyConditionField.CAPABILITY_CLASS:
        return "" if request.capability_class is None else request.capability_class.value
    if field is PolicyConditionField.ACTOR_ORGANIZATION_ID:
        return request.actor_organization_id
    if field is PolicyConditionField.ACTOR_ENVIRONMENT_ID:
        return request.actor_environment_id
    if field is PolicyConditionField.TARGET_ORGANIZATION_ID:
        return request.target_organization_id
    if field is PolicyConditionField.TARGET_ENVIRONMENT_ID:
        return request.target_environment_id
    if field is PolicyConditionField.ACTOR_IS_AI:
        return "true" if request.actor_is_ai else "false"
    if field is PolicyConditionField.CONNECTOR_TRUST:
        return request.connector_trust.value
    return request.approval_status.value  # APPROVAL_STATUS


@dataclass(frozen=True, slots=True)
class PolicyCondition:
    field: PolicyConditionField
    operator: PolicyConditionOperator
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("a policy condition requires at least one value")
        if (
            self.operator in (PolicyConditionOperator.EQUALS, PolicyConditionOperator.NOT_EQUALS)
            and len(self.values) != 1
        ):
            raise ValueError("equals/not_equals conditions take exactly one value")

    def matches(self, request: PolicyDecisionRequest) -> bool:
        value = _field_value(request, self.field)
        if self.operator is PolicyConditionOperator.EQUALS:
            return value == self.values[0]
        if self.operator is PolicyConditionOperator.NOT_EQUALS:
            return value != self.values[0]
        if self.operator is PolicyConditionOperator.IN:
            return value in self.values
        return value not in self.values  # NOT_IN


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """One rule inside a PolicySet. Conditions combine with AND; an empty tuple matches every
    request, which is how a layer authors an unconditional fallback (e.g. a Platform-layer
    catch-all deny)."""

    rule_id: str
    effect: PolicyDecisionOutcome
    conditions: tuple[PolicyCondition, ...]
    summary: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.rule_id, "rule_id")
        if not self.summary.strip():
            raise ValueError("a policy rule requires a summary")

    def matches(self, request: PolicyDecisionRequest) -> bool:
        return all(condition.matches(request) for condition in self.conditions)


def compute_rule_document_digest(rules: tuple[PolicyRule, ...]) -> str:
    """A canonical SHA-256 digest of one rule set's content, independent of Python object
    identity -- the same rules in the same order always produce the same digest, matching how
    this project's other content-addressed evidence digests are computed (e.g. the vendor
    connector clients' response digests)."""
    canonical = [
        {
            "rule_id": rule.rule_id,
            "effect": rule.effect.value,
            "conditions": [
                {
                    "field": condition.field.value,
                    "operator": condition.operator.value,
                    "values": list(condition.values),
                }
                for condition in rule.conditions
            ],
            "summary": rule.summary,
        }
        for rule in rules
    ]
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
