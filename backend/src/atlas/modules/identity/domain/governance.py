from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.identity.domain.api_credentials import ApiCredentialRecord
from atlas.modules.identity.domain.sessions import SessionRecord


@dataclass(frozen=True, slots=True)
class IdentityGovernanceInventory:
    sessions: tuple[SessionRecord, ...]
    api_credentials: tuple[ApiCredentialRecord, ...]
    truncated: bool
