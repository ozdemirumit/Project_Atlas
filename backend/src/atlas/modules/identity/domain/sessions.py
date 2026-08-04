from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import AuthenticatedSubject, validate_stable_identifier


class CredentialKind(StrEnum):
    BROWSER_SESSION = "browser_session"
    API_TOKEN = "api_token"


class SessionState(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: str
    version: int
    credential_kind: CredentialKind
    token_digest: str = field(repr=False)
    csrf_digest: str = field(repr=False)
    subject: AuthenticatedSubject
    created_at: datetime
    last_seen_at: datetime
    absolute_expires_at: datetime
    idle_expires_at: datetime
    state: SessionState
    revoked_at: datetime | None = None
    revocation_reason: str | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.session_id, "session_id")
        if self.version < 1:
            raise ValueError("session version must be positive")
        if len(self.token_digest) != 64 or len(self.csrf_digest) != 64:
            raise ValueError("session credentials require SHA-256 digests")
        timestamps = (
            self.created_at,
            self.last_seen_at,
            self.absolute_expires_at,
            self.idle_expires_at,
        )
        if any(item.tzinfo is None for item in timestamps):
            raise ValueError("session timestamps must be timezone-aware")
        if not self.created_at <= self.last_seen_at < self.absolute_expires_at:
            raise ValueError("session absolute lifetime is invalid")
        if not self.last_seen_at < self.idle_expires_at <= self.absolute_expires_at:
            raise ValueError("session idle lifetime is invalid")
        if self.state is SessionState.ACTIVE and (
            self.revoked_at is not None or self.revocation_reason is not None
        ):
            raise ValueError("active session cannot carry revocation metadata")
        if self.state is not SessionState.ACTIVE and (
            self.revoked_at is None or not self.revocation_reason
        ):
            raise ValueError("terminated session requires revocation metadata")


@dataclass(frozen=True, slots=True)
class IssuedSession:
    record: SessionRecord
    token: str = field(repr=False)
    csrf_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class SessionContext:
    subject: AuthenticatedSubject
    session_id: str
    credential_kind: CredentialKind
    absolute_expires_at: datetime
    idle_expires_at: datetime
