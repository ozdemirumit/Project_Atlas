from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.api_credential_schemas import ApiCredentialGrantData
from atlas.api.schemas import ResponseMeta
from atlas.modules.identity.domain.api_credentials import ApiCredentialRecord
from atlas.modules.identity.domain.sessions import SessionRecord


class IdentityGovernanceSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    version: int
    subject_id: str
    subject_display_name: str
    provider_id: str
    state: str
    credential_kind: str
    created_at: datetime
    last_seen_at: datetime
    absolute_expires_at: datetime
    idle_expires_at: datetime

    @classmethod
    def from_domain(cls, record: SessionRecord) -> IdentityGovernanceSession:
        return cls(
            session_id=record.session_id,
            version=record.version,
            subject_id=record.subject.subject_id,
            subject_display_name=record.subject.display_name,
            provider_id=record.subject.provider_id,
            state=record.state.value,
            credential_kind=record.credential_kind.value,
            created_at=record.created_at,
            last_seen_at=record.last_seen_at,
            absolute_expires_at=record.absolute_expires_at,
            idle_expires_at=record.idle_expires_at,
        )


class IdentityGovernanceApiCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: str
    version: int
    subject_id: str
    subject_display_name: str
    provider_id: str
    display_name: str
    purpose: str
    state: str
    grants: list[ApiCredentialGrantData]
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None

    @classmethod
    def from_domain(cls, record: ApiCredentialRecord) -> IdentityGovernanceApiCredential:
        return cls(
            credential_id=record.credential_id,
            version=record.version,
            subject_id=record.subject.subject_id,
            subject_display_name=record.subject.display_name,
            provider_id=record.subject.provider_id,
            display_name=record.display_name,
            purpose=record.purpose,
            state=record.state.value,
            grants=[
                ApiCredentialGrantData(
                    permission_id=grant.permission_id,
                    scope_reference=grant.scope_reference,
                )
                for grant in record.grants
            ],
            created_at=record.created_at,
            expires_at=record.expires_at,
            last_used_at=record.last_used_at,
        )


class IdentityGovernanceInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions: list[IdentityGovernanceSession]
    api_credentials: list[IdentityGovernanceApiCredential]
    truncated: bool


class IdentityGovernanceInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: IdentityGovernanceInventoryData
    meta: ResponseMeta


class AdministrativeRevocationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=240, pattern=r"^[^\x00-\x1f\x7f]+$")


class IdentityGovernanceSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: IdentityGovernanceSession
    meta: ResponseMeta


class IdentityGovernanceApiCredentialResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: IdentityGovernanceApiCredential
    meta: ResponseMeta
