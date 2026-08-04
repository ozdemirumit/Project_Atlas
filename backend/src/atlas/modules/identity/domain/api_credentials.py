from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import (
    AuthenticatedSubject,
    CredentialGrant,
    validate_stable_identifier,
)


class ApiCredentialState(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class ApiCredentialRecord:
    credential_id: str
    version: int
    token_digest: str = field(repr=False, compare=False)
    subject: AuthenticatedSubject
    display_name: str
    purpose: str
    grants: tuple[CredentialGrant, ...]
    created_at: datetime
    expires_at: datetime
    state: ApiCredentialState
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.credential_id, "credential_id")
        if self.version < 1:
            raise ValueError("credential version must be positive")
        if len(self.token_digest) != 64:
            raise ValueError("API credential requires a SHA-256 digest")
        if not 1 <= len(self.display_name.strip()) <= 80:
            raise ValueError("credential display name is outside platform bounds")
        if not 1 <= len(self.purpose.strip()) <= 240:
            raise ValueError("credential purpose is outside platform bounds")
        if not 1 <= len(self.grants) <= 10 or len(set(self.grants)) != len(self.grants):
            raise ValueError("credential grants are invalid")
        if tuple(
            sorted(self.grants, key=lambda item: (item.permission_id, item.scope_reference))
        ) != (self.grants):
            raise ValueError("credential grants must be deterministically ordered")
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("credential timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("credential expiry must follow creation")
        if self.last_used_at is not None:
            if self.last_used_at.tzinfo is None:
                raise ValueError("last_used_at must be timezone-aware")
            if not self.created_at <= self.last_used_at < self.expires_at:
                raise ValueError("last_used_at is outside credential lifetime")
        if self.state is ApiCredentialState.ACTIVE and (
            self.revoked_at is not None or self.revocation_reason is not None
        ):
            raise ValueError("active credential cannot carry revocation metadata")
        if self.state is not ApiCredentialState.ACTIVE:
            if self.revoked_at is None or not self.revocation_reason:
                raise ValueError("terminated credential requires revocation metadata")
            if self.revoked_at.tzinfo is None:
                raise ValueError("revoked_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class IssuedApiCredential:
    record: ApiCredentialRecord
    token: str = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ApiCredentialContext:
    subject: AuthenticatedSubject
    credential_id: str
    grants: frozenset[CredentialGrant]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ApiCredentialInventory:
    records: tuple[ApiCredentialRecord, ...]
    truncated: bool
