from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class WorkloadIdentityState(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class WorkloadCredentialState(StrEnum):
    ACTIVE = "active"
    RETIRING = "retiring"
    REVOKED = "revoked"
    EXPIRED = "expired"


def _validate_values(values: tuple[str, ...], field_name: str, *, maximum: int) -> None:
    if not 1 <= len(values) <= maximum or len(set(values)) != len(values):
        raise ValueError(f"{field_name} is invalid")
    if tuple(sorted(values)) != values:
        raise ValueError(f"{field_name} must be deterministically ordered")
    for value in values:
        validate_stable_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class WorkloadIdentityRecord:
    identity_id: str
    version: int
    display_name: str
    service_id: str
    instance_id: str
    owner_subject_id: str
    purpose: str
    organization_id: str
    environment_id: str
    audiences: tuple[str, ...]
    secret_reference_ids: tuple[str, ...]
    state: WorkloadIdentityState
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.identity_id, "identity_id"),
            (self.service_id, "service_id"),
            (self.instance_id, "instance_id"),
            (self.owner_subject_id, "owner_subject_id"),
            (self.organization_id, "organization_id"),
            (self.environment_id, "environment_id"),
        ):
            validate_stable_identifier(value, name)
        if self.version < 1:
            raise ValueError("workload identity version must be positive")
        if not 1 <= len(self.display_name.strip()) <= 80:
            raise ValueError("workload identity display name is outside platform bounds")
        if not 1 <= len(self.purpose.strip()) <= 240:
            raise ValueError("workload identity purpose is outside platform bounds")
        _validate_values(self.audiences, "audience", maximum=10)
        _validate_values(self.secret_reference_ids, "secret_reference_id", maximum=20)
        if any(not value.startswith("secret.") for value in self.secret_reference_ids):
            raise ValueError("workload secrets must use opaque secret references")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("workload identity timestamps must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("workload identity update precedes creation")


@dataclass(frozen=True, slots=True)
class WorkloadCredentialRecord:
    credential_id: str
    version: int
    identity_id: str
    token_digest: str = field(repr=False, compare=False)
    key_version: int
    audiences: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    state: WorkloadCredentialState
    retire_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.credential_id, "credential_id")
        validate_stable_identifier(self.identity_id, "identity_id")
        if self.version < 1 or self.key_version < 1:
            raise ValueError("workload credential versions must be positive")
        if len(self.token_digest) != 64:
            raise ValueError("workload credential requires a SHA-256 digest")
        _validate_values(self.audiences, "audience", maximum=10)
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("workload credential timestamps must be timezone-aware")
        if self.expires_at <= self.issued_at:
            raise ValueError("workload credential expiry must follow issuance")
        if self.state is WorkloadCredentialState.RETIRING:
            if self.retire_at is None or not self.issued_at < self.retire_at <= self.expires_at:
                raise ValueError("retiring credential requires a bounded retirement time")
        elif self.retire_at is not None:
            raise ValueError("only retiring credentials carry retirement time")
        if self.state is WorkloadCredentialState.REVOKED:
            if self.revoked_at is None or not self.revocation_reason:
                raise ValueError("revoked credential requires revocation metadata")
        elif self.revoked_at is not None or self.revocation_reason is not None:
            raise ValueError("active credential cannot carry revocation metadata")


@dataclass(frozen=True, slots=True)
class IssuedWorkloadCredential:
    identity: WorkloadIdentityRecord
    credential: WorkloadCredentialRecord
    token: str = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class WorkloadIdentityInventory:
    identities: tuple[WorkloadIdentityRecord, ...]
    credentials: tuple[WorkloadCredentialRecord, ...]
    truncated: bool
