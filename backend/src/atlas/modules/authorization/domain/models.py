from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.capabilities import CapabilityClass as CapabilityClass
from atlas.modules.identity.domain.models import AuthenticatedSubject, validate_stable_identifier


class DecisionOutcome(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    permission_id: str
    description: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.permission_id, "permission_id")
        if not self.description.strip():
            raise ValueError("permission description must not be empty")


@dataclass(frozen=True, slots=True)
class ResourceScope:
    organization_id: str
    environment_id: str
    site_id: str
    domain_id: str
    resource_id: str
    capability_class: CapabilityClass

    def __post_init__(self) -> None:
        validate_stable_identifier(self.organization_id, "organization_id")
        validate_stable_identifier(self.environment_id, "environment_id")
        validate_stable_identifier(self.site_id, "site_id")
        validate_stable_identifier(self.domain_id, "domain_id")
        validate_stable_identifier(self.resource_id, "resource_id")

    @property
    def reference(self) -> str:
        return "/".join(
            (
                self.organization_id,
                self.environment_id,
                self.site_id,
                self.domain_id,
                self.resource_id,
                self.capability_class.value,
            )
        )


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    role_id: str
    version: int
    permissions: frozenset[str]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.role_id, "role_id")
        if self.version < 1:
            raise ValueError("role version must be positive")
        for permission in self.permissions:
            validate_stable_identifier(permission, "permission")

    @property
    def version_reference(self) -> str:
        return f"{self.role_id}:v{self.version}"


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    assignment_id: str
    version: int
    subject_id: str
    role_id: str
    scope: ResourceScope
    valid_from: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.assignment_id, "assignment_id")
        validate_stable_identifier(self.subject_id, "subject_id")
        validate_stable_identifier(self.role_id, "role_id")
        if self.version < 1:
            raise ValueError("assignment version must be positive")
        if self.valid_from.tzinfo is None:
            raise ValueError("valid_from must be timezone-aware")
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError("expires_at must be timezone-aware")
            if self.expires_at <= self.valid_from:
                raise ValueError("expires_at must be later than valid_from")

    @property
    def version_reference(self) -> str:
        return f"{self.assignment_id}:v{self.version}"

    def is_active(self, at: datetime) -> bool:
        return self.valid_from <= at and (self.expires_at is None or at < self.expires_at)


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    subject: AuthenticatedSubject
    permission_id: str
    resource_type: str
    scope: ResourceScope
    correlation_id: str
    requested_at: datetime
    target_subject_id: str | None = None
    reason: str | None = None
    idempotency_key: str | None = None
    target_metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        validate_stable_identifier(self.permission_id, "permission_id")
        validate_stable_identifier(self.resource_type, "resource_type")
        if self.requested_at.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    decision_id: str
    decided_at: datetime
    outcome: DecisionOutcome
    reason_code: str
    permission_id: str
    scope_reference: str
    subject_id: str
    role_references: tuple[str, ...]
    assignment_references: tuple[str, ...]
    correlation_id: str

    @property
    def allowed(self) -> bool:
        return self.outcome is DecisionOutcome.ALLOWED
