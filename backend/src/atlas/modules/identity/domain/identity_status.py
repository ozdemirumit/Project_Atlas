from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import AuthenticatedSubject


class IdentityLifecycleState(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class IdentityStatusRecord:
    subject: AuthenticatedSubject
    version: int
    state: IdentityLifecycleState
    observed_at: datetime
    disabled_at: datetime | None = None
    disabled_by: str | None = None
    disable_reason: str | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("identity status version must be positive")
        if self.observed_at.tzinfo is None:
            raise ValueError("identity observation time must be timezone-aware")
        disabled_fields = (self.disabled_at, self.disabled_by, self.disable_reason)
        if self.state is IdentityLifecycleState.ACTIVE and any(
            item is not None for item in disabled_fields
        ):
            raise ValueError("active identity cannot carry disablement metadata")
        if self.state is IdentityLifecycleState.DISABLED:
            if any(item is None for item in disabled_fields):
                raise ValueError("disabled identity requires complete disablement metadata")
            if self.disabled_at is not None and self.disabled_at.tzinfo is None:
                raise ValueError("identity disablement time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class IdentityDisablementResult:
    status: IdentityStatusRecord
    revoked_session_count: int
    revoked_api_credential_count: int

    def __post_init__(self) -> None:
        if self.status.state is not IdentityLifecycleState.DISABLED:
            raise ValueError("disablement result requires disabled identity state")
        if self.revoked_session_count < 0 or self.revoked_api_credential_count < 0:
            raise ValueError("revoked credential counts cannot be negative")
