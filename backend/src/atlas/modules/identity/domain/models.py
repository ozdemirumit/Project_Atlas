from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

STABLE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")


def validate_stable_identifier(value: str, field_name: str) -> None:
    if not STABLE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field_name} is not a valid stable identifier")


class SubjectKind(StrEnum):
    HUMAN = "human"
    SERVICE = "service"
    CONNECTOR = "connector"


class AuthenticationMethod(StrEnum):
    DEVELOPMENT = "development"
    LDAP = "ldap"
    OIDC = "oidc"
    SAML = "saml"
    MUTUAL_TLS = "mutual_tls"
    API_TOKEN = "api_token"
    WORKLOAD_TOKEN = "workload_token"


class AssuranceLevel(StrEnum):
    DEVELOPMENT = "development"
    SINGLE_FACTOR = "single_factor"
    MULTI_FACTOR = "multi_factor"
    HARDWARE_BACKED = "hardware_backed"


_ASSURANCE_ORDER = {
    AssuranceLevel.DEVELOPMENT: 0,
    AssuranceLevel.SINGLE_FACTOR: 1,
    AssuranceLevel.MULTI_FACTOR: 2,
    AssuranceLevel.HARDWARE_BACKED: 3,
}


def assurance_satisfies_policy(actual: AssuranceLevel, required: AssuranceLevel) -> bool:
    """Evaluate an explicit step-up policy without making assurance an authorization grant."""
    if required is AssuranceLevel.SINGLE_FACTOR and actual is AssuranceLevel.DEVELOPMENT:
        return True
    return _ASSURANCE_ORDER[actual] >= _ASSURANCE_ORDER[required]


class IdentityProviderFailure(RuntimeError):
    def __init__(
        self,
        *,
        provider_id: str,
        authentication_method: AuthenticationMethod,
        result_code: str,
    ) -> None:
        super().__init__(result_code)
        validate_stable_identifier(provider_id, "provider_id")
        validate_stable_identifier(result_code, "result_code")
        self.provider_id = provider_id
        self.authentication_method = authentication_method
        self.result_code = result_code


class IdentityProviderDenied(RuntimeError):
    def __init__(
        self,
        *,
        provider_id: str,
        authentication_method: AuthenticationMethod,
        result_code: str = "credentials_rejected",
    ) -> None:
        super().__init__(result_code)
        validate_stable_identifier(provider_id, "provider_id")
        validate_stable_identifier(result_code, "result_code")
        self.provider_id = provider_id
        self.authentication_method = authentication_method
        self.result_code = result_code


@dataclass(frozen=True, slots=True)
class AuthenticationInput:
    correlation_id: str
    authorization_scheme: str | None = None
    credential: str | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class CredentialGrant:
    permission_id: str
    scope_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.permission_id, "permission_id")
        if not 1 <= len(self.scope_reference) <= 1024:
            raise ValueError("scope_reference is outside platform bounds")
        if any(ord(character) < 32 for character in self.scope_reference):
            raise ValueError("scope_reference contains control characters")


@dataclass(frozen=True, slots=True)
class AuthenticatedSubject:
    subject_id: str
    display_name: str
    kind: SubjectKind
    provider_id: str
    authentication_method: AuthenticationMethod
    assurance_level: AssuranceLevel
    authenticated_at: datetime
    organization_id: str
    role_ids: tuple[str, ...]
    group_ids: tuple[str, ...] = ()
    credential_grants: frozenset[CredentialGrant] | None = field(
        default=None,
        repr=False,
    )

    def __post_init__(self) -> None:
        validate_stable_identifier(self.subject_id, "subject_id")
        validate_stable_identifier(self.provider_id, "provider_id")
        validate_stable_identifier(self.organization_id, "organization_id")
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if self.authenticated_at.tzinfo is None:
            raise ValueError("authenticated_at must be timezone-aware")
        for role_id in self.role_ids:
            validate_stable_identifier(role_id, "role_id")
        for group_id in self.group_ids:
            validate_stable_identifier(group_id, "group_id")
