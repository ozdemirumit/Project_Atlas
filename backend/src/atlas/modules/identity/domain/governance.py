from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.identity.domain.api_credentials import ApiCredentialRecord
from atlas.modules.identity.domain.identity_status import IdentityStatusRecord
from atlas.modules.identity.domain.sessions import SessionRecord


@dataclass(frozen=True, slots=True)
class IdentityGovernanceSubject:
    status: IdentityStatusRecord
    active_session_count: int
    active_api_credential_count: int


@dataclass(frozen=True, slots=True)
class IdentityGovernanceInventory:
    subjects: tuple[IdentityGovernanceSubject, ...]
    sessions: tuple[SessionRecord, ...]
    api_credentials: tuple[ApiCredentialRecord, ...]
    truncated: bool
