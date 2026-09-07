"""ATLAS-059 SS9/SS10: the release lifecycle and roles/accountability."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReleaseLifecycleState(StrEnum):
    """SS9's fourteen lifecycle states."""

    PLANNING = "planning"
    DEVELOPING = "developing"
    FEATURE_COMPLETE = "feature_complete"
    CANDIDATE = "candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    DEPLOYING = "deploying"
    SUPPORTED = "supported"
    ROLLED_BACK = "rolled_back"
    MAINTENANCE = "maintenance"
    DEPRECATED = "deprecated"
    END_OF_SUPPORT = "end_of_support"
    RETIRED = "retired"


_ALLOWED_TRANSITIONS: dict[ReleaseLifecycleState, frozenset[ReleaseLifecycleState]] = {
    ReleaseLifecycleState.PLANNING: frozenset({ReleaseLifecycleState.DEVELOPING}),
    ReleaseLifecycleState.DEVELOPING: frozenset({ReleaseLifecycleState.FEATURE_COMPLETE}),
    ReleaseLifecycleState.FEATURE_COMPLETE: frozenset({ReleaseLifecycleState.CANDIDATE}),
    ReleaseLifecycleState.CANDIDATE: frozenset(
        {
            ReleaseLifecycleState.CANDIDATE,
            ReleaseLifecycleState.APPROVED,
            ReleaseLifecycleState.REJECTED,
        }
    ),
    ReleaseLifecycleState.APPROVED: frozenset({ReleaseLifecycleState.PUBLISHED}),
    ReleaseLifecycleState.REJECTED: frozenset(),
    ReleaseLifecycleState.PUBLISHED: frozenset({ReleaseLifecycleState.DEPLOYING}),
    ReleaseLifecycleState.DEPLOYING: frozenset(
        {ReleaseLifecycleState.SUPPORTED, ReleaseLifecycleState.ROLLED_BACK}
    ),
    ReleaseLifecycleState.SUPPORTED: frozenset({ReleaseLifecycleState.MAINTENANCE}),
    ReleaseLifecycleState.ROLLED_BACK: frozenset({ReleaseLifecycleState.CANDIDATE}),
    ReleaseLifecycleState.MAINTENANCE: frozenset({ReleaseLifecycleState.DEPRECATED}),
    ReleaseLifecycleState.DEPRECATED: frozenset({ReleaseLifecycleState.END_OF_SUPPORT}),
    ReleaseLifecycleState.END_OF_SUPPORT: frozenset({ReleaseLifecycleState.RETIRED}),
    ReleaseLifecycleState.RETIRED: frozenset(),
}


def is_valid_transition(
    *, from_state: ReleaseLifecycleState, to_state: ReleaseLifecycleState
) -> bool:
    """SS9's lifecycle diagram, reproduced as an explicit adjacency table. Unlike every other
    lifecycle table this session has built, `CANDIDATE -> CANDIDATE` ("new RC after correction")
    is a real, diagram-declared self-transition, not an omission -- self-loops are checked per
    state rather than blanket-rejected."""
    return to_state in _ALLOWED_TRANSITIONS[from_state]


class ReleaseRole(StrEnum):
    """SS10's ten roles."""

    PRODUCT_OWNER = "product_owner"
    RELEASE_MANAGER = "release_manager"
    ARCHITECTURE_OWNER = "architecture_owner"
    SECURITY_OWNER = "security_owner"
    QUALITY_OWNER = "quality_owner"
    AI_OWNER = "ai_owner"
    PLATFORM_OWNER = "platform_owner"
    DOMAIN_OWNERS = "domain_owners"
    OPERATIONS_AND_SUPPORT_OWNERS = "operations_and_support_owners"
    AUDIT_AND_COMPLIANCE_REVIEWER = "audit_and_compliance_reviewer"


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    role: ReleaseRole
    assigned_identity: str

    def __post_init__(self) -> None:
        if not self.assigned_identity.strip():
            raise ValueError("a role assignment requires an assigned identity")


def separation_of_duties_applies_to_high_risk_exceptions_and_production_approval() -> bool:
    """SS10: "separation of duties applies to high-risk exceptions and production
    approval.\""""
    return True
