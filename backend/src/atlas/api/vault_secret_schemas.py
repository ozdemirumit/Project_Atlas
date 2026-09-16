from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.vault_secret import (
    SECRET_REFERENCE_ID_PATTERN,
    ConnectorVaultSecretReference,
)


class ConnectorVaultSecretInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: SecretStr = Field(min_length=1, max_length=8_192, exclude=True, repr=False)


class ConnectorVaultSecretReferenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret_reference_id: str = Field(pattern=SECRET_REFERENCE_ID_PATTERN.pattern)
    updated_at: datetime
    set_by_subject_digest: str
    secret_material_disclosed: bool = False

    @classmethod
    def from_domain(
        cls, reference: ConnectorVaultSecretReference
    ) -> ConnectorVaultSecretReferenceData:
        return cls(
            secret_reference_id=reference.secret_reference_id,
            updated_at=reference.updated_at,
            set_by_subject_digest=reference.set_by_subject_digest,
        )


class ConnectorVaultSecretListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorVaultSecretReferenceData, ...]
    meta: ResponseMeta


class ConnectorVaultSecretWriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorVaultSecretReferenceData
    meta: ResponseMeta
