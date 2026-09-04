"""ATLAS-025 SS14/SS15: versioned policy sets and their deterministic resolution.

This slice adds the store's domain shape and a pure resolution function -- given every known
policy set and one request's scope, which sets are in play, in what order. Resolution itself
still does not evaluate any rule content -- that is `policy_engine.domain.evaluation`'s job, once
resolution has already narrowed candidates down to the ones actually in play.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.policy_engine.domain.rule import PolicyRule


class PolicySetLayer(StrEnum):
    """The nine layers ATLAS-025 SS14 lists, in the order the document lists them -- that order
    is also this module's resolution order, from most general to most specific."""

    PLATFORM = "platform"
    DEPLOYMENT = "deployment"
    ORGANIZATION = "organization"
    ENVIRONMENT = "environment"
    SITE = "site"
    DOMAIN = "domain"
    CONNECTOR_CAPABILITY = "connector_capability"
    SERVICE = "service"
    WORKFLOW = "workflow"


class PolicyLifecycleState(StrEnum):
    """ATLAS-025 SS15. Only a set in ACTIVE state affects production decisions; every other
    state is administrative (authoring, review, scheduling) or terminal (suspended/retired)."""

    DRAFT = "draft"
    VALIDATING = "validating"
    SIMULATION = "simulation"
    REVIEW = "review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class PolicySetScope:
    """What a policy set applies to. A field left as None matches every value for that field --
    a Platform-layer set with every field None applies to all requests; an Organization-layer
    set sets only organization_id, applying to every environment/site/... within it."""

    organization_id: str | None = None
    environment_id: str | None = None
    site_id: str | None = None
    domain_id: str | None = None
    connector_id: str | None = None
    capability_id: str | None = None
    service_id: str | None = None
    workflow_id: str | None = None


@dataclass(frozen=True, slots=True)
class PolicySet:
    set_id: str
    version: int
    layer: PolicySetLayer
    lifecycle_state: PolicyLifecycleState
    scope: PolicySetScope
    rule_document_digest: str
    effective_from: datetime
    effective_until: datetime | None = None
    rules: tuple[PolicyRule, ...] = ()

    def __post_init__(self) -> None:
        validate_stable_identifier(self.set_id, "set_id")
        if self.version < 1:
            raise ValueError("policy set version must be positive")
        if len(self.rule_document_digest) != 64:
            raise ValueError("policy set requires a SHA-256 rule-document digest")
        if self.effective_from.tzinfo is None:
            raise ValueError("effective_from must be timezone-aware")
        if self.effective_until is not None:
            if self.effective_until.tzinfo is None:
                raise ValueError("effective_until must be timezone-aware")
            if self.effective_until <= self.effective_from:
                raise ValueError("effective_until must be later than effective_from")

    @property
    def version_reference(self) -> str:
        return f"{self.set_id}:v{self.version}"

    def is_active_at(self, at: datetime) -> bool:
        if self.lifecycle_state is not PolicyLifecycleState.ACTIVE:
            return False
        if at < self.effective_from:
            return False
        return not (self.effective_until is not None and at >= self.effective_until)


@dataclass(frozen=True, slots=True)
class PolicySetResolutionScope:
    """The scope one policy decision request resolves policy sets against. organization_id and
    environment_id are always present; the remaining fields are only as specific as the request
    actually is (e.g. a request with no workflow context leaves workflow_id None, which simply
    never matches a Workflow-layer set's own non-None workflow_id)."""

    organization_id: str
    environment_id: str
    site_id: str | None = None
    domain_id: str | None = None
    connector_id: str | None = None
    capability_id: str | None = None
    service_id: str | None = None
    workflow_id: str | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.organization_id, "organization_id")
        validate_stable_identifier(self.environment_id, "environment_id")


_LAYER_ORDER: dict[PolicySetLayer, int] = {
    layer: index for index, layer in enumerate(PolicySetLayer)
}


def _matches(scope: PolicySetScope, request: PolicySetResolutionScope) -> bool:
    for scope_value, request_value in (
        (scope.organization_id, request.organization_id),
        (scope.environment_id, request.environment_id),
        (scope.site_id, request.site_id),
        (scope.domain_id, request.domain_id),
        (scope.connector_id, request.connector_id),
        (scope.capability_id, request.capability_id),
        (scope.service_id, request.service_id),
        (scope.workflow_id, request.workflow_id),
    ):
        if scope_value is not None and scope_value != request_value:
            return False
    return True


def resolve_policy_sets(
    candidates: Iterable[PolicySet],
    *,
    scope: PolicySetResolutionScope,
    at: datetime,
) -> tuple[PolicySet, ...]:
    """ATLAS-025 SS14: deterministic resolution of which policy sets apply to one request scope
    at one instant. Only ACTIVE sets (SS15) whose own scope matches (a None field on the set's
    scope matches anything) are included, ordered from the most general layer to the most
    specific -- the order SS14 itself lists the nine layers in -- then by set_id as a stable
    tie-break within a layer. This does not evaluate any rule content; it only decides which
    versioned sets are in play, which a later slice's evaluation engine then combines."""
    matched = [
        candidate
        for candidate in candidates
        if candidate.is_active_at(at) and _matches(candidate.scope, scope)
    ]
    matched.sort(key=lambda candidate: (_LAYER_ORDER[candidate.layer], candidate.set_id))
    return tuple(matched)
