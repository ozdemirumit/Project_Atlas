from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.identity.domain.api_credentials import ApiCredentialRecord


class ApiCredentialCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=240)
    expires_in_minutes: int = Field(ge=5, le=60)
    permission_ids: list[str] = Field(min_length=1, max_length=10)


class ApiCredentialGrantData(BaseModel):
    permission_id: str
    scope_reference: str


class ApiCredentialData(BaseModel):
    credential_id: str
    version: int
    display_name: str
    purpose: str
    state: str
    grants: list[ApiCredentialGrantData]
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None

    @classmethod
    def from_domain(cls, record: ApiCredentialRecord) -> ApiCredentialData:
        return cls(
            credential_id=record.credential_id,
            version=record.version,
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


class IssuedApiCredentialData(ApiCredentialData):
    token: str = Field(repr=False)


class ApiCredentialInventoryData(BaseModel):
    credentials: list[ApiCredentialData]
    available_grants: list[ApiCredentialGrantData]
    truncated: bool


class ApiCredentialCreateResponse(BaseModel):
    data: IssuedApiCredentialData
    meta: ResponseMeta


class ApiCredentialInventoryResponse(BaseModel):
    data: ApiCredentialInventoryData
    meta: ResponseMeta
