from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from atlas.api.schemas import ResponseMeta
from atlas.modules.identity.domain.sessions import SessionRecord


class SessionCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    password: SecretStr = Field(min_length=1, max_length=1024)


class SessionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    version: int
    state: str
    credential_kind: str
    subject_id: str
    created_at: datetime
    absolute_expires_at: datetime
    idle_expires_at: datetime

    @classmethod
    def from_domain(cls, record: SessionRecord) -> SessionData:
        return cls(
            session_id=record.session_id,
            version=record.version,
            state=record.state.value,
            credential_kind=record.credential_kind.value,
            subject_id=record.subject.subject_id,
            created_at=record.created_at,
            absolute_expires_at=record.absolute_expires_at,
            idle_expires_at=record.idle_expires_at,
        )


class SessionCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: SessionData
    meta: ResponseMeta


class SessionInventoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    version: int
    state: str
    credential_kind: str
    created_at: datetime
    last_seen_at: datetime
    absolute_expires_at: datetime
    idle_expires_at: datetime
    current: bool

    @classmethod
    def from_domain(cls, record: SessionRecord, *, current_session_id: str | None) -> Self:
        return cls(
            session_id=record.session_id,
            version=record.version,
            state=record.state.value,
            credential_kind=record.credential_kind.value,
            created_at=record.created_at,
            last_seen_at=record.last_seen_at,
            absolute_expires_at=record.absolute_expires_at,
            idle_expires_at=record.idle_expires_at,
            current=record.session_id == current_session_id,
        )


class SessionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions: list[SessionInventoryItem]
    truncated: bool


class SessionInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: SessionInventoryData
    meta: ResponseMeta
