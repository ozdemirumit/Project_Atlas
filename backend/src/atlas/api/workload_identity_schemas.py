from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.schemas import ResponseMeta
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.identity.domain.workload_identities import (
    IssuedWorkloadCredential,
    WorkloadCredentialRecord,
    WorkloadIdentityRecord,
)

STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]{2,127}$"


class WorkloadIdentityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_id: str
    version: int
    display_name: str
    service_id: str
    instance_id: str
    owner_subject_id: str
    purpose: str
    organization_id: str
    environment_id: str
    audiences: list[str]
    secret_reference_ids: list[str]
    state: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, record: WorkloadIdentityRecord) -> WorkloadIdentityData:
        return cls(
            identity_id=record.identity_id,
            version=record.version,
            display_name=record.display_name,
            service_id=record.service_id,
            instance_id=record.instance_id,
            owner_subject_id=record.owner_subject_id,
            purpose=record.purpose,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            audiences=list(record.audiences),
            secret_reference_ids=list(record.secret_reference_ids),
            state=record.state.value,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class WorkloadCredentialData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_id: str
    version: int
    identity_id: str
    key_version: int
    audiences: list[str]
    issued_at: datetime
    expires_at: datetime
    state: str
    retire_at: datetime | None
    revoked_at: datetime | None

    @classmethod
    def from_domain(cls, record: WorkloadCredentialRecord) -> WorkloadCredentialData:
        return cls(
            credential_id=record.credential_id,
            version=record.version,
            identity_id=record.identity_id,
            key_version=record.key_version,
            audiences=list(record.audiences),
            issued_at=record.issued_at,
            expires_at=record.expires_at,
            state=record.state.value,
            retire_at=record.retire_at,
            revoked_at=record.revoked_at,
        )


class WorkloadIdentityInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identities: list[WorkloadIdentityData]
    credentials: list[WorkloadCredentialData]
    truncated: bool


class WorkloadIdentityInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: WorkloadIdentityInventoryData
    meta: ResponseMeta


class CreateWorkloadIdentityPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_id: str = Field(pattern=STABLE_ID_PATTERN)
    display_name: str = Field(min_length=1, max_length=80, pattern=r"^[^\x00-\x1f\x7f]+$")
    service_id: str = Field(pattern=STABLE_ID_PATTERN)
    instance_id: str = Field(pattern=STABLE_ID_PATTERN)
    owner_subject_id: str = Field(pattern=STABLE_ID_PATTERN)
    purpose: str = Field(min_length=1, max_length=240, pattern=r"^[^\x00-\x1f\x7f]+$")
    audiences: list[str] = Field(min_length=1, max_length=10)
    secret_reference_ids: list[str] = Field(min_length=1, max_length=20)
    lifetime_minutes: int = Field(ge=1, le=30)
    reason: str = Field(min_length=1, max_length=240, pattern=r"^[^\x00-\x1f\x7f]+$")

    @field_validator("audiences")
    @classmethod
    def validate_audiences(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("audiences must be unique")
        for value in values:
            if not re.fullmatch(STABLE_ID_PATTERN, value):
                raise ValueError("audience must be a stable identifier")
        return values

    @field_validator("secret_reference_ids")
    @classmethod
    def validate_secret_references(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("secret references must be unique")
        for value in values:
            if not value.startswith("secret.") or not re.fullmatch(STABLE_ID_PATTERN, value):
                raise ValueError("secrets must use opaque stable references")
        return values


class RotateWorkloadCredentialPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    lifetime_minutes: int = Field(ge=1, le=30)
    overlap_minutes: int = Field(ge=0, le=5)
    reason: str = Field(min_length=1, max_length=240, pattern=r"^[^\x00-\x1f\x7f]+$")


class RevokeWorkloadCredentialPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=240, pattern=r"^[^\x00-\x1f\x7f]+$")


class IssuedWorkloadCredentialData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: WorkloadIdentityData
    credential: WorkloadCredentialData
    token: str

    @classmethod
    def from_domain(cls, issued: IssuedWorkloadCredential) -> IssuedWorkloadCredentialData:
        return cls(
            identity=WorkloadIdentityData.from_domain(issued.identity),
            credential=WorkloadCredentialData.from_domain(issued.credential),
            token=issued.token,
        )


class IssuedWorkloadCredentialResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: IssuedWorkloadCredentialData
    meta: ResponseMeta


class WorkloadCredentialResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: WorkloadCredentialData
    meta: ResponseMeta


class CurrentWorkloadIdentityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    display_name: str
    subject_kind: str
    organization_id: str
    authentication_method: str
    audience: str
    environment_id: str
    role_ids: list[str]
    execution_authorized: bool = False

    @classmethod
    def from_domain(
        cls, subject: AuthenticatedSubject, *, audience: str, environment_id: str
    ) -> CurrentWorkloadIdentityData:
        return cls(
            subject_id=subject.subject_id,
            display_name=subject.display_name,
            subject_kind=subject.kind.value,
            organization_id=subject.organization_id,
            authentication_method=subject.authentication_method.value,
            audience=audience,
            environment_id=environment_id,
            role_ids=list(subject.role_ids),
        )


class CurrentWorkloadIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: CurrentWorkloadIdentityData
    meta: ResponseMeta
